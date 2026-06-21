#!/usr/bin/env python
from __future__ import annotations

import argparse
import concurrent.futures
import json
from pathlib import Path
import sys
import textwrap
import time
from typing import Any, Dict, Iterable, List

from multi_model_runtime import (
    add_common_arguments,
    aggregate_usage_and_cost,
    check_cost_cap,
    codex_home,
    dry_run_output,
    eprint,
    filter_available_members,
    finalize_run,
    format_skipped,
    get_available_model_ids,
    load_price_config,
    local_run_id,
    manual_fallback_answer,
    parse_csv,
    read_prompt,
    resolve_members,
    run_model,
    run_status,
    start_router,
    successful,
    truncate,
    utc_now_iso,
)


SKILL_NAME = "TawabaranPro - Synth Model"

PANEL = [
    {"key": "gpt55pro", "label": "GPT 5.5 Pro", "model": "gpt-5.5", "reasoning_effort": "xhigh", "env_key": "OPENAI_API_KEY"},
    {"key": "opus48max", "label": "Claude Opus 4.8 Max", "model": "opus-4.8-max", "reasoning_effort": "max", "env_key": "ANTHROPIC_API_KEY"},
    {"key": "deepseek", "label": "DeepSeek V4 Pro", "model": "deepseek-v4-pro", "reasoning_effort": "xhigh", "env_key": "DEEPSEEK_API_KEY"},
    {"key": "glm52", "label": "GLM 5.2", "model": "glm-5.2", "reasoning_effort": "xhigh", "env_key": "ZAI_API_KEY"},
    {"key": "gemini31deepthink", "label": "Gemini 3.1 Pro Deep Think", "model": "gemini-3.1-pro-deep-think", "reasoning_effort": "high", "env_key": "GEMINI_API_KEY"},
]


def respondent_messages(user_task: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are an independent expert respondent in a multi-model panel. "
                "Answer the user's task directly. Do not mention other panelists. "
                "Do not wait for, simulate, or request a discussion. Produce your best standalone answer."
            ),
        },
        {"role": "user", "content": user_task},
    ]


def synthesis_messages(user_task: str, results: Iterable[Dict[str, Any]], max_chars: int) -> List[Dict[str, str]]:
    blocks: List[str] = []
    for result in results:
        status = result.get("status")
        if status == "success":
            body = truncate(str(result.get("content") or ""), max_chars)
        else:
            body = f"[{status}] model={result.get('model')}\n{truncate(str(result.get('error') or ''), 2000)}"
        blocks.append(f"## {result.get('label')} ({status})\n{body}")

    synthesis_task = textwrap.dedent(
        f"""
        User task:
        {user_task}

        Independent model answers:
        {chr(10).join(blocks)}
        """
    ).strip()
    return [
        {
            "role": "system",
            "content": (
                "Synthesize independent model answers into one final answer. "
                "Do not create a debate or discussion round. Weigh the answers critically, resolve contradictions, "
                "and prefer concrete actionable conclusions. Answer in the same language as the user's task unless asked otherwise. "
                "If any model failed, mention that briefly."
            ),
        },
        {"role": "user", "content": synthesis_task},
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run model APIs in parallel and synthesize the result.")
    add_common_arguments(parser)
    parser.add_argument("--cwd", default=".", help="Reserved for compatibility; API mode does not use it.")
    parser.add_argument("--no-synthesis", action="store_true", help="Run respondents only.")
    return parser.parse_args()


def prepare_runtime(args: argparse.Namespace) -> Dict[str, Any]:
    if not (args.dry_run and args.skip_model_check):
        eprint("[panel] starting LiteLLM router")
        start_router(__file__)

    available_ids = None
    if not args.skip_model_check:
        eprint("[panel] checking LiteLLM /v1/models")
        available_ids = get_available_model_ids(min(args.timeout, 30))

    requested_models = parse_csv(args.models)
    requested_synth = [args.synthesizer] + parse_csv(args.synthesizer_fallbacks)

    selected, unknown_models = resolve_members(PANEL, requested_models)
    synthesizers, unknown_synths = resolve_members(PANEL, requested_synth)

    selected, skipped_models = filter_available_members(
        selected,
        available_ids,
        check_api_keys=not args.no_api_key_check,
        check_model_registry=not args.skip_model_check,
    )
    synthesizers, skipped_synths = filter_available_members(
        synthesizers,
        available_ids,
        check_api_keys=not args.no_api_key_check,
        check_model_registry=not args.skip_model_check,
    )

    skipped = skipped_models + skipped_synths + unknown_models + unknown_synths
    return {"selected": selected, "synthesizers": synthesizers, "skipped": skipped, "available_ids": available_ids}


def run_synthesis(
    synthesizers: List[Dict[str, str]],
    messages: List[Dict[str, str]],
    out_dir: Path,
    args: argparse.Namespace,
    prices: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for member in synthesizers:
        eprint(f"[panel] synthesizing with {member['label']} ({member['model']})")
        result = run_model(
            member,
            messages,
            out_dir,
            f"synthesis.{member['key']}",
            args.synthesis_timeout,
            args.retries,
            args.retry_backoff,
            prices,
        )
        attempts.append(result)
        if result.get("status") == "success":
            return {"final": result, "attempts": attempts}
    return {"final": attempts[-1] if attempts else {}, "attempts": attempts}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    user_task = read_prompt(args).strip()
    if not user_task and not args.dry_run:
        raise SystemExit("Prompt is empty.")

    runtime = prepare_runtime(args)
    selected = runtime["selected"]
    synthesizers = runtime["synthesizers"]
    skipped = runtime["skipped"]

    if args.dry_run:
        print(json.dumps(dry_run_output(skill_name=SKILL_NAME, selected=selected, skipped=skipped, synthesizers=synthesizers, prompt=user_task), ensure_ascii=False, indent=2))
        return 0

    if not selected:
        raise SystemExit("No usable respondent models. Check --models, API keys, and LiteLLM /v1/models.")
    if not args.no_synthesis and not synthesizers:
        eprint("[panel] no usable synthesizer; the run will return respondent answers only")

    run_id = local_run_id()
    out_dir = Path(args.out_dir) if args.out_dir else codex_home() / "tmp" / "multi-model-synthesis" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "task.txt").write_text(user_task, encoding="utf-8")
    prices = load_price_config(args.price_config)
    started = time.monotonic()

    eprint(f"[panel] output directory: {out_dir}")
    eprint(f"[panel] launching {len(selected)} model API calls")
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(selected)) as executor:
        futures = [
            executor.submit(run_model, member, respondent_messages(user_task), out_dir, f"initial.{member['key']}", args.timeout, args.retries, args.retry_backoff, prices)
            for member in selected
        ]
        results = [future.result() for future in futures]

    success_count = len(successful(results))
    eprint(f"[panel] respondent success: {success_count}/{len(selected)}")
    if success_count < len(selected) and not args.allow_partial:
        eprint("[panel] partial failures found and --no-allow-partial is set")

    run_record: Dict[str, Any] = {
        "run_id": run_id,
        "mode": "direct-litellm-chat-completions-api",
        "started_at": utc_now_iso(),
        "task_path": str(out_dir / "task.txt"),
        "output_dir": str(out_dir),
        "models_requested": parse_csv(args.models) or [item["model"] for item in PANEL],
        "models_used": [item["model"] for item in selected],
        "models_skipped": format_skipped(skipped),
        "panel": selected,
        "results": results,
    }

    if success_count == 0:
        run_record["status"] = "failed"
        final_content = "All respondent models failed. See report.md and errors/ for details."
        finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
        print(final_content)
        return 2

    stage_cost = aggregate_usage_and_cost(run_record)
    if args.max_cost_usd is not None and stage_cost["estimated_cost_usd_known"] > args.max_cost_usd:
        run_record["status"] = "partial_success"
        final_content = manual_fallback_answer("Cost cap reached before synthesis", results, args.max_chars_per_response)
        finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
        print(final_content)
        return 4

    if args.no_synthesis or not synthesizers:
        run_record["status"] = run_status(results)
        final_content = manual_fallback_answer("Synthesis", results, args.max_chars_per_response)
        finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
        print(final_content)
        return 0 if args.allow_partial or success_count == len(selected) else 2

    synthesis = run_synthesis(synthesizers, synthesis_messages(user_task, results, args.max_chars_per_response), out_dir, args, prices)
    run_record["synthesis"] = synthesis["final"]
    run_record["synthesis_attempts"] = synthesis["attempts"]
    final = synthesis["final"]

    if final.get("status") == "success":
        run_record["status"] = run_status(results) if success_count < len(selected) else "success"
        final_content = str(final.get("content") or "").strip()
    else:
        run_record["status"] = "partial_success"
        final_content = manual_fallback_answer("Synthesis", results, args.max_chars_per_response)

    metadata = finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
    if check_cost_cap(metadata, args.max_cost_usd):
        eprint(f"[panel] known estimated cost exceeded --max-cost-usd: {metadata['estimated_cost_usd_known']}")
    print(final_content)
    return 0 if args.allow_partial or success_count == len(selected) else 2


if __name__ == "__main__":
    raise SystemExit(main())
