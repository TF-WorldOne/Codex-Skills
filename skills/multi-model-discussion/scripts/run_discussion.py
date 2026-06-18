#!/usr/bin/env python
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time
from typing import Any, Dict, Iterable, List
import urllib.error
import urllib.request


ROUTER_BASE_URL = "http://127.0.0.1:4141/v1"

PANEL = [
    {"key": "gpt55pro", "label": "GPT 5.5 Pro", "model": "gpt-5.5", "reasoning_effort": "xhigh"},
    {"key": "opus48max", "label": "Claude Opus 4.8 Max", "model": "opus-4.8-max", "reasoning_effort": "max"},
    {"key": "deepseek", "label": "DeepSeek V4 Pro", "model": "deepseek-v4-pro", "reasoning_effort": "xhigh"},
    {"key": "glm52", "label": "GLM 5.2", "model": "glm-5.2", "reasoning_effort": "xhigh"},
    {
        "key": "gemini31deepthink",
        "label": "Gemini 3.1 Pro Deep Think",
        "model": "gemini-3.1-pro-deep-think",
        "reasoning_effort": "high",
    },
]

SYNTHESIZER = {
    "key": "synthesis",
    "label": "GPT 5.5 Pro Synthesis",
    "model": "gpt-5.5",
    "reasoning_effort": "xhigh",
}


def eprint(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide --prompt, --prompt-file, or stdin.")


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")


def router_script() -> Path:
    override = os.environ.get("CODEX_MULTI_MODEL_ROUTER_SCRIPT")
    if override and Path(override).is_file():
        return Path(override)

    bundled = Path(__file__).resolve().parents[3] / "scripts" / "start-router.ps1"
    if bundled.is_file():
        return bundled

    return codex_home() / "start-glm52-router.ps1"


def start_router() -> None:
    script = router_script()
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


def api_post(path: str, payload: Dict[str, Any], timeout: int) -> Dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        f"{ROUTER_BASE_URL}{path}",
        data=body,
        method="POST",
        headers={"Authorization": "Bearer local", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read().decode("utf-8", errors="replace")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        data = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {data}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc)) from exc


def extract_content(response: Dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                value = item.get("text") or item.get("content")
                if isinstance(value, str):
                    parts.append(value)
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content).strip() if content else ""


def run_model(
    member: Dict[str, str],
    messages: List[Dict[str, str]],
    output_dir: Path,
    output_key: str,
    timeout: int,
) -> Dict[str, Any]:
    start = time.monotonic()
    last_message = output_dir / f"{output_key}.last.md"
    response_path = output_dir / f"{output_key}.response.json"
    error_path = output_dir / f"{output_key}.error.log"

    payload: Dict[str, Any] = {"model": member["model"], "messages": messages}
    effort = member.get("reasoning_effort")
    if effort:
        payload["reasoning_effort"] = effort

    try:
        response = api_post("/chat/completions", payload, timeout)
        response_path.write_text(json.dumps(response, ensure_ascii=False, indent=2), encoding="utf-8")
        content = extract_content(response)
        last_message.write_text(content, encoding="utf-8")
        return {
            "key": member["key"],
            "output_key": output_key,
            "label": member["label"],
            "model": member["model"],
            "status": "success" if content else "empty",
            "duration_seconds": round(time.monotonic() - start, 2),
            "last_message_path": str(last_message),
            "response_path": str(response_path),
            "error_path": str(error_path),
            "content": content,
            "usage": response.get("usage"),
        }
    except Exception as exc:
        error_path.write_text(str(exc), encoding="utf-8")
        return {
            "key": member["key"],
            "output_key": output_key,
            "label": member["label"],
            "model": member["model"],
            "status": "failed",
            "duration_seconds": round(time.monotonic() - start, 2),
            "last_message_path": str(last_message),
            "response_path": str(response_path),
            "error_path": str(error_path),
            "content": "",
            "error": str(exc),
        }


def truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n\n[TRUNCATED after {limit} characters]"


def format_results(title: str, results: Iterable[Dict[str, Any]], max_chars: int) -> str:
    blocks: List[str] = [f"# {title}"]
    for result in results:
        status = result.get("status")
        if status == "success":
            body = truncate(str(result.get("content") or ""), max_chars)
        else:
            body = f"[{status}] model={result.get('model')}\n{truncate(str(result.get('error') or ''), 2000)}"
        blocks.append(f"## {result.get('label')} ({status})\n{body}")
    return "\n\n".join(blocks)


def initial_messages(user_task: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an independent expert respondent in a multi-model panel. "
                "Answer the user's task directly. Do not mention other panelists yet. "
                "Produce your best standalone answer."
            ),
        },
        {"role": "user", "content": user_task},
    ]


def discussion_messages(
    user_task: str,
    member: Dict[str, str],
    initial_results: List[Dict[str, Any]],
    previous_discussion_results: List[Dict[str, Any]],
    round_number: int,
    max_chars: int,
) -> List[Dict[str, str]]:
    context_parts = [
        format_results("Initial independent answers", initial_results, max_chars),
    ]
    if previous_discussion_results:
        context_parts.append(
            format_results(f"Previous discussion round {round_number - 1}", previous_discussion_results, max_chars)
        )

    user_content = textwrap.dedent(
        f"""
        Original task:
        {user_task}

        You are {member['label']}. Review the other models' answers and any previous discussion.
        Critique weak assumptions, identify what should change, and give your revised position.
        Do not roleplay the other models. Do not merely summarize; update your answer after seeing the panel.

        {chr(10).join(context_parts)}
        """
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "You are participating in a structured multi-model discussion. "
                "Be direct, critical, and constructive. Revise your own answer after reading the panel."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def synthesis_messages(
    user_task: str,
    initial_results: List[Dict[str, Any]],
    discussion_rounds: List[List[Dict[str, Any]]],
    max_chars: int,
) -> List[Dict[str, str]]:
    context_parts = [format_results("Initial independent answers", initial_results, max_chars)]
    for index, round_results in enumerate(discussion_rounds, start=1):
        context_parts.append(format_results(f"Discussion round {index}", round_results, max_chars))

    synthesis_task = textwrap.dedent(
        f"""
        User task:
        {user_task}

        Panel materials:
        {chr(10).join(context_parts)}
        """
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "You are GPT 5.5 Pro. Synthesize the full multi-model panel discussion into one final answer. "
                "Weigh the initial answers and discussion revisions critically, resolve contradictions, and prefer concrete conclusions. "
                "Answer in the same language as the user's task unless asked otherwise. Mention failures only if relevant."
            ),
        },
        {"role": "user", "content": synthesis_task},
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run five model APIs, discuss, then synthesize with GPT 5.5.")
    parser.add_argument("--prompt", help="Task text to send to the panel.")
    parser.add_argument("--prompt-file", help="UTF-8 text file containing the task.")
    parser.add_argument("--out-dir", help="Directory for run artifacts.")
    parser.add_argument("--timeout", type=int, default=900, help="Timeout in seconds for each model API call.")
    parser.add_argument("--synthesis-timeout", type=int, default=900, help="Timeout in seconds for GPT 5.5 synthesis.")
    parser.add_argument("--discussion-rounds", type=int, default=1, help="Number of discussion/revision rounds after initial answers.")
    parser.add_argument("--max-chars-per-response", type=int, default=60000, help="Per-model character cap in prompts.")
    parser.add_argument("--no-synthesis", action="store_true", help="Run discussion only.")
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    user_task = read_prompt(args).strip()
    if not user_task:
        raise SystemExit("Prompt is empty.")
    if args.discussion_rounds < 1:
        raise SystemExit("--discussion-rounds must be at least 1.")

    out_dir = Path(args.out_dir) if args.out_dir else codex_home() / "tmp" / "multi-model-discussion" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "task.txt").write_text(user_task, encoding="utf-8")

    eprint(f"[discussion] output directory: {out_dir}")
    eprint("[discussion] starting LiteLLM router")
    start_router()

    eprint("[discussion] launching initial model API calls")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(PANEL)) as executor:
        initial_results = [
            future.result()
            for future in [
                executor.submit(run_model, member, initial_messages(user_task), out_dir, f"initial.{member['key']}", args.timeout)
                for member in PANEL
            ]
        ]

    discussion_rounds: List[List[Dict[str, Any]]] = []
    previous_round: List[Dict[str, Any]] = []
    for round_number in range(1, args.discussion_rounds + 1):
        eprint(f"[discussion] launching discussion round {round_number}")
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(PANEL)) as executor:
            round_results = [
                future.result()
                for future in [
                    executor.submit(
                        run_model,
                        member,
                        discussion_messages(
                            user_task,
                            member,
                            initial_results,
                            previous_round,
                            round_number,
                            args.max_chars_per_response,
                        ),
                        out_dir,
                        f"discussion{round_number}.{member['key']}",
                        args.timeout,
                    )
                    for member in PANEL
                ]
            ]
        discussion_rounds.append(round_results)
        previous_round = round_results

    run_record: Dict[str, Any] = {
        "mode": "direct-litellm-chat-completions-api-with-discussion",
        "task_path": str(out_dir / "task.txt"),
        "output_dir": str(out_dir),
        "panel": PANEL,
        "initial_results": initial_results,
        "discussion_rounds": discussion_rounds,
    }

    if args.no_synthesis:
        (out_dir / "run.json").write_text(json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(run_record, ensure_ascii=False, indent=2))
        return 0

    eprint("[discussion] synthesizing with GPT 5.5 Pro API")
    final = run_model(
        SYNTHESIZER,
        synthesis_messages(user_task, initial_results, discussion_rounds, args.max_chars_per_response),
        out_dir,
        SYNTHESIZER["key"],
        args.synthesis_timeout,
    )
    run_record["synthesis"] = final
    (out_dir / "run.json").write_text(json.dumps(run_record, ensure_ascii=False, indent=2), encoding="utf-8")

    if final.get("status") == "success":
        print(str(final.get("content") or "").strip())
        return 0

    eprint(f"[discussion] synthesis failed. See: {out_dir}")
    print(json.dumps(run_record, ensure_ascii=False, indent=2))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
