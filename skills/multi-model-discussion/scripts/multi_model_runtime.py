from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import urllib.error
import urllib.request


ROUTER_BASE_URL = "http://127.0.0.1:4141/v1"


def eprint(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def local_run_id() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def router_script(current_file: str) -> Path:
    override = os.environ.get("CODEX_MULTI_MODEL_ROUTER_SCRIPT")
    if override and Path(override).is_file():
        return Path(override)

    bundled = Path(current_file).resolve().parents[3] / "scripts" / "start-router.ps1"
    if bundled.is_file():
        return bundled

    return codex_home() / "start-glm52-router.ps1"


def start_router(current_file: str) -> None:
    script = router_script(current_file)
    if not script.is_file():
        raise SystemExit(f"LiteLLM router start script not found: {script}")

    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise SystemExit(
            "Failed to start LiteLLM router.\n"
            f"STDOUT:\n{proc.stdout}\n"
            f"STDERR:\n{proc.stderr}"
        )


def get_user_env(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value:
        return value
    if os.name != "nt":
        return None
    try:
        import winreg  # type: ignore

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value) if value else None
    except Exception:
        return None


def parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    if getattr(args, "dry_run", False):
        return ""
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --prompt, --prompt-file, or stdin.")


def api_request(method: str, path: str, timeout: int, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{ROUTER_BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Authorization": "Bearer local", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {raw}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc)) from exc


def get_available_model_ids(timeout: int) -> List[str]:
    data = api_request("GET", "/models", timeout)
    models = data.get("data") or []
    ids: List[str] = []
    for item in models:
        if isinstance(item, dict):
            value = item.get("id") or item.get("model_name")
            if value:
                ids.append(str(value))
    return sorted(set(ids))


def member_aliases(member: Dict[str, str]) -> List[str]:
    return [
        str(member.get("key", "")),
        str(member.get("model", "")),
        str(member.get("label", "")),
    ]


def resolve_members(catalog: Sequence[Dict[str, str]], names: Sequence[str]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    if not names:
        return [dict(item) for item in catalog], []

    selected: List[Dict[str, str]] = []
    unknown: List[Dict[str, str]] = []
    for name in names:
        needle = name.casefold()
        match = None
        for item in catalog:
            if any(alias.casefold() == needle for alias in member_aliases(item)):
                match = dict(item)
                break
        if match:
            if not any(existing["model"] == match["model"] for existing in selected):
                selected.append(match)
        else:
            unknown.append({"name": name, "reason": "unknown_model"})
    return selected, unknown


def filter_available_members(
    members: Sequence[Dict[str, str]],
    available_model_ids: Optional[Sequence[str]],
    *,
    check_api_keys: bool,
    check_model_registry: bool,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    available_set = set(available_model_ids or [])
    enabled: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    for member in members:
        reasons: List[str] = []
        env_key = member.get("env_key")
        if check_api_keys and env_key and not get_user_env(env_key):
            reasons.append(f"missing_env:{env_key}")
        if check_model_registry and available_model_ids is not None and member["model"] not in available_set:
            reasons.append("not_in_litellm_models")
        if reasons:
            item = dict(member)
            item["reason"] = ",".join(reasons)
            skipped.append(item)
        else:
            enabled.append(dict(member))
    return enabled, skipped


def load_price_config(path: Optional[str]) -> Dict[str, Dict[str, float]]:
    config_path = path or os.environ.get("CODEX_MULTI_MODEL_PRICE_CONFIG")
    if not config_path:
        return {}
    data = json.loads(Path(config_path).read_text(encoding="utf-8"))
    prices: Dict[str, Dict[str, float]] = {}
    for model, values in data.items():
        if isinstance(values, dict):
            prices[str(model)] = {
                "input_per_1m": float(values.get("input_per_1m", 0) or 0),
                "output_per_1m": float(values.get("output_per_1m", 0) or 0),
            }
    return prices


def normalize_usage(usage: Optional[Dict[str, Any]]) -> Dict[str, int]:
    usage = usage or {}
    input_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0)) or 0
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0)) or 0
    total_tokens = usage.get("total_tokens") or int(input_tokens) + int(output_tokens)
    return {
        "input_tokens": int(input_tokens),
        "output_tokens": int(output_tokens),
        "total_tokens": int(total_tokens),
    }


def response_cost(response: Dict[str, Any]) -> Optional[float]:
    candidates = [
        response.get("response_cost"),
        response.get("cost"),
        (response.get("_hidden_params") or {}).get("response_cost") if isinstance(response.get("_hidden_params"), dict) else None,
    ]
    for value in candidates:
        if isinstance(value, (int, float)):
            return float(value)
    return None


def estimate_cost_usd(model: str, usage: Dict[str, int], prices: Dict[str, Dict[str, float]], response: Dict[str, Any]) -> Optional[float]:
    direct = response_cost(response)
    if direct is not None:
        return round(direct, 8)
    price = prices.get(model)
    if not price:
        return None
    cost = (
        usage["input_tokens"] * price.get("input_per_1m", 0) / 1_000_000
        + usage["output_tokens"] * price.get("output_per_1m", 0) / 1_000_000
    )
    return round(cost, 8)


def should_retry(error: Exception) -> bool:
    text = str(error)
    retry_markers = ["HTTP 429", "HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "timed out", "Connection", "disconnect"]
    return any(marker.lower() in text.lower() for marker in retry_markers)


def extract_content(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content).strip() if content else ""


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def write_json(path: Path, value: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def run_model(
    member: Dict[str, str],
    messages: List[Dict[str, str]],
    output_dir: Path,
    output_key: str,
    timeout: int,
    retries: int,
    retry_backoff: float,
    prices: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    start = time.monotonic()
    last_message = output_dir / "models" / f"{output_key}.md"
    response_path = output_dir / "raw" / f"{output_key}.response.json"
    error_path = output_dir / "errors" / f"{output_key}.error.log"

    payload: Dict[str, Any] = {"model": member["model"], "messages": messages}
    effort = member.get("reasoning_effort")
    if effort:
        payload["reasoning_effort"] = effort

    attempts = max(0, retries) + 1
    last_error: Optional[Exception] = None
    for attempt in range(1, attempts + 1):
        try:
            response = api_request("POST", "/chat/completions", timeout, payload)
            write_json(response_path, response)
            content = extract_content(response)
            write_text(last_message, content)
            usage = normalize_usage(response.get("usage"))
            return {
                "key": member["key"],
                "output_key": output_key,
                "label": member["label"],
                "model": member["model"],
                "status": "success" if content else "empty",
                "attempts": attempt,
                "duration_seconds": round(time.monotonic() - start, 2),
                "last_message_path": str(last_message),
                "response_path": str(response_path),
                "error_path": str(error_path),
                "content": content,
                "usage": usage,
                "estimated_cost_usd": estimate_cost_usd(member["model"], usage, prices, response),
            }
        except Exception as exc:
            last_error = exc
            if attempt < attempts and should_retry(exc):
                time.sleep(retry_backoff * (2 ** (attempt - 1)))
                continue
            break

    error_text = str(last_error) if last_error else "unknown error"
    write_text(error_path, error_text)
    status = "timeout" if "timed out" in error_text.lower() else "failed"
    return {
        "key": member["key"],
        "output_key": output_key,
        "label": member["label"],
        "model": member["model"],
        "status": status,
        "attempts": attempts,
        "duration_seconds": round(time.monotonic() - start, 2),
        "last_message_path": str(last_message),
        "response_path": str(response_path),
        "error_path": str(error_path),
        "content": "",
        "error": error_text,
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "estimated_cost_usd": None,
    }


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n\n[TRUNCATED after {limit} characters]"


def successful(results: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [item for item in results if item.get("status") == "success" and item.get("content")]


def flatten_results(value: Any) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    if isinstance(value, list):
        for item in value:
            items.extend(flatten_results(item))
    elif isinstance(value, dict):
        if "status" in value and "model" in value:
            items.append(value)
        for child_key in ("results", "initial_results", "discussion_rounds", "synthesis_attempts"):
            if child_key in value:
                items.extend(flatten_results(value[child_key]))
        if isinstance(value.get("synthesis"), dict):
            items.extend(flatten_results(value["synthesis"]))
    return items


def aggregate_usage_and_cost(run_record: Dict[str, Any]) -> Dict[str, Any]:
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    known_cost = 0.0
    unknown_cost_models: List[str] = []
    for result in flatten_results(run_record):
        usage = normalize_usage(result.get("usage"))
        for key in totals:
            totals[key] += usage[key]
        cost = result.get("estimated_cost_usd")
        if isinstance(cost, (int, float)):
            known_cost += float(cost)
        elif result.get("status") == "success":
            unknown_cost_models.append(str(result.get("model")))
    return {
        "usage": totals,
        "estimated_cost_usd_known": round(known_cost, 8),
        "cost_estimate_incomplete": bool(unknown_cost_models),
        "unknown_cost_models": sorted(set(unknown_cost_models)),
    }


def run_status(results: Iterable[Dict[str, Any]]) -> str:
    items = list(results)
    if not items:
        return "failed"
    success_count = sum(1 for item in items if item.get("status") == "success")
    if success_count == len(items):
        return "success"
    if success_count > 0:
        return "partial_success"
    return "failed"


def format_skipped(skipped: Iterable[Dict[str, str]]) -> List[Dict[str, str]]:
    return [
        {
            "key": item.get("key", item.get("name", "")),
            "label": item.get("label", item.get("name", "")),
            "model": item.get("model", ""),
            "reason": item.get("reason", ""),
        }
        for item in skipped
    ]


def build_report(skill_name: str, run_record: Dict[str, Any], final_content: str) -> str:
    meta = run_record.get("metadata", {})
    lines = [
        f"# {skill_name} Run Report",
        "",
        f"- Run ID: `{meta.get('run_id', '')}`",
        f"- Status: `{meta.get('status', '')}`",
        f"- Started: `{meta.get('started_at', '')}`",
        f"- Ended: `{meta.get('ended_at', '')}`",
        f"- Duration seconds: `{meta.get('duration_seconds', '')}`",
        f"- Models used: `{', '.join(meta.get('models_used', []))}`",
        f"- Models skipped: `{len(meta.get('models_skipped', []))}`",
        f"- Input tokens: `{meta.get('usage', {}).get('input_tokens', 0)}`",
        f"- Output tokens: `{meta.get('usage', {}).get('output_tokens', 0)}`",
        f"- Known estimated cost USD: `{meta.get('estimated_cost_usd_known', 0)}`",
        f"- Cost estimate incomplete: `{meta.get('cost_estimate_incomplete', False)}`",
        "",
        "## Final Answer",
        "",
        final_content.strip() or "(no final answer)",
        "",
        "## Model Results",
        "",
    ]
    for result in flatten_results(run_record):
        if result.get("output_key", "").startswith("synthesis.") or result.get("output_key") == "synthesis":
            continue
        lines.append(f"- {result.get('label')} / `{result.get('model')}`: `{result.get('status')}` in `{result.get('duration_seconds')}`s")
    return "\n".join(lines).rstrip() + "\n"


def manual_fallback_answer(title: str, results: Iterable[Dict[str, Any]], max_chars: int) -> str:
    blocks = [
        f"{title} failed, so the available successful model answers are returned below.",
        "",
    ]
    for result in successful(results):
        blocks.append(f"## {result.get('label')} ({result.get('model')})")
        blocks.append(truncate(str(result.get("content") or ""), max_chars))
        blocks.append("")
    return "\n".join(blocks).strip()


def finalize_run(
    *,
    skill_name: str,
    run_record: Dict[str, Any],
    output_dir: Path,
    started_monotonic: float,
    final_content: str,
) -> Dict[str, Any]:
    status = run_record.get("status") or run_status(flatten_results(run_record))
    aggregates = aggregate_usage_and_cost(run_record)
    metadata = {
        "run_id": run_record.get("run_id"),
        "skill": skill_name,
        "status": status,
        "started_at": run_record.get("started_at"),
        "ended_at": utc_now_iso(),
        "duration_seconds": round(time.monotonic() - started_monotonic, 2),
        "output_dir": str(output_dir),
        "models_requested": run_record.get("models_requested", []),
        "models_used": run_record.get("models_used", []),
        "models_skipped": run_record.get("models_skipped", []),
        **aggregates,
    }
    run_record["metadata"] = metadata
    write_text(output_dir / "final.md", final_content.strip() + "\n" if final_content.strip() else "")
    write_json(output_dir / "metadata.json", metadata)
    write_json(output_dir / "run.json", run_record)
    write_text(output_dir / "report.md", build_report(skill_name, run_record, final_content))
    return metadata


def dry_run_output(
    *,
    skill_name: str,
    selected: Sequence[Dict[str, str]],
    skipped: Sequence[Dict[str, str]],
    synthesizers: Sequence[Dict[str, str]],
    prompt: str,
    discussion_rounds: int = 0,
) -> Dict[str, Any]:
    approx_input_tokens = max(1, len(prompt) // 4) if prompt else 0
    return {
        "skill": skill_name,
        "dry_run": True,
        "models_used": [{"label": item["label"], "model": item["model"]} for item in selected],
        "models_skipped": format_skipped(skipped),
        "synthesizer_order": [{"label": item["label"], "model": item["model"]} for item in synthesizers],
        "discussion_rounds": discussion_rounds,
        "approx_prompt_tokens": approx_input_tokens,
        "api_calls_planned": len(selected) * (1 + discussion_rounds) + (0 if not synthesizers else 1),
    }


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--prompt", help="Task text to send to the panel.")
    parser.add_argument("--prompt-file", help="UTF-8 text file containing the task.")
    parser.add_argument("--models", help="Comma-separated model keys or LiteLLM model names to use.")
    parser.add_argument("--synthesizer", default="gpt-5.5", help="Model key or LiteLLM model name used for final synthesis.")
    parser.add_argument(
        "--synthesizer-fallbacks",
        default="opus-4.8-max,gemini-3.1-pro-deep-think,deepseek-v4-pro,glm-5.2",
        help="Comma-separated fallback synthesizers tried after --synthesizer fails.",
    )
    parser.add_argument("--out-dir", "--output-dir", dest="out_dir", help="Directory for run artifacts.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for each model API call.")
    parser.add_argument("--synthesis-timeout", type=int, default=900, help="Timeout in seconds for synthesis model API calls.")
    parser.add_argument("--retries", type=int, default=1, help="Retries per model after the first failed attempt.")
    parser.add_argument("--retry-backoff", type=float, default=2.0, help="Initial retry backoff seconds; doubles each retry.")
    parser.add_argument("--allow-partial", dest="allow_partial", action="store_true", default=True, help="Continue when some models fail. Default: on.")
    parser.add_argument("--no-allow-partial", dest="allow_partial", action="store_false", help="Fail when any selected model fails.")
    parser.add_argument("--skip-model-check", action="store_true", help="Skip LiteLLM /v1/models availability filtering.")
    parser.add_argument("--no-api-key-check", action="store_true", help="Do not filter models by local API key environment variables.")
    parser.add_argument("--dry-run", action="store_true", help="Show selected models and planned calls without chat completions.")
    parser.add_argument("--price-config", help="JSON file with per-model input_per_1m/output_per_1m prices for cost estimates.")
    parser.add_argument("--max-cost-usd", type=float, help="Abort after a stage if known estimated cost exceeds this cap.")
    parser.add_argument("--max-chars-per-response", type=int, default=60000, help="Per-model character cap in synthesis prompts.")


def check_cost_cap(metadata: Dict[str, Any], max_cost_usd: Optional[float]) -> bool:
    if max_cost_usd is None:
        return False
    known = metadata.get("estimated_cost_usd_known")
    return isinstance(known, (int, float)) and float(known) > max_cost_usd
