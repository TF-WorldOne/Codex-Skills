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


SKILL_NAME = "TawabaranPro - Discussion Model"

PANEL = [
    {"key": "gpt55pro", "label": "GPT 5.5 Pro", "model": "gpt-5.5", "reasoning_effort": "xhigh", "env_key": "OPENAI_API_KEY"},
    {"key": "opus48max", "label": "Claude Opus 4.8 Max", "model": "opus-4.8-max", "reasoning_effort": "max", "env_key": "ANTHROPIC_API_KEY"},
    {"key": "deepseek", "label": "DeepSeek V4 Pro", "model": "deepseek-v4-pro", "reasoning_effort": "xhigh", "env_key": "DEEPSEEK_API_KEY"},
    {"key": "glm52", "label": "GLM 5.2", "model": "glm-5.2", "reasoning_effort": "xhigh", "env_key": "ZAI_API_KEY"},
    {"key": "gemini31deepthink", "label": "Gemini 3.1 Pro Deep Think", "model": "gemini-3.1-pro-deep-think", "reasoning_effort": "high", "env_key": "GEMINI_API_KEY"},
]


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
    context_parts = [format_results("Initial independent answers", initial_results, max_chars)]
    if previous_discussion_results:
        context_parts.append(format_results(f"Previous discussion round {round_number - 1}", previous_discussion_results, max_chars))

    user_content = textwrap.dedent(
        f"""
        Original task:
        {user_task}

        You are {member['label']}. Review the other models' answers and any previous discussion.
        Do not roleplay the other models. Do not merely summarize; update your answer after seeing the panel.

        Use this exact structure:
        1. Agreements
        2. Disagreements
        3. Missing points
        4. Corrections to your initial answer
        5. Final recommendation
        6. Confidence

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
                "Synthesize the full multi-model panel discussion into one final answer. "
                "Separate consensus, disagreements, minority views, adopted conclusion, and reasoning when useful. "
                "Resolve contradictions and prefer concrete conclusions. Answer in the same language as the user's task unless asked otherwise. "
                "Mention failures only if relevant."
            ),
        },
        {"role": "user", "content": synthesis_task},
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run model APIs, discuss, then synthesize.")
    add_common_arguments(parser)
    parser.add_argument("--discussion-rounds", type=int, default=1, help="Number of discussion/revision rounds after initial answers.")
    parser.add_argument("--no-synthesis", action="store_true", help="Run discussion only.")
    return parser.parse_args()


def prepare_runtime(args: argparse.Namespace) -> Dict[str, Any]:
    if not (args.dry_run and args.skip_model_check):
        eprint("[discussion] starting LiteLLM router")
        start_router(__file__)

    available_ids = None
    if not args.skip_model_check:
        eprint("[discussion] checking LiteLLM /v1/models")
        available_ids = get_available_model_ids(min(args.timeout, 30))

    selected, unknown_models = resolve_members(PANEL, parse_csv(args.models))
    synthesizers, unknown_synths = resolve_members(PANEL, [args.synthesizer] + parse_csv(args.synthesizer_fallbacks))

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
    return {"selected": selected, "synthesizers": synthesizers, "skipped": skipped_models + skipped_synths + unknown_models + unknown_synths}


def run_round(
    *,
    members: List[Dict[str, str]],
    messages_by_member: Dict[str, List[Dict[str, str]]],
    out_dir: Path,
    output_prefix: str,
    args: argparse.Namespace,
    prices: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(members)) as executor:
        futures = [
            executor.submit(
                run_model,
                member,
                messages_by_member[member["key"]],
                out_dir,
                f"{output_prefix}.{member['key']}",
                args.timeout,
                args.retries,
                args.retry_backoff,
                prices,
            )
            for member in members
        ]
        return [future.result() for future in futures]


def run_synthesis(
    synthesizers: List[Dict[str, str]],
    messages: List[Dict[str, str]],
    out_dir: Path,
    args: argparse.Namespace,
    prices: Dict[str, Dict[str, float]],
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    for member in synthesizers:
        eprint(f"[discussion] synthesizing with {member['label']} ({member['model']})")
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


def active_members_from_results(members: List[Dict[str, str]], results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    success_keys = {item.get("key") for item in successful(results)}
    return [member for member in members if member["key"] in success_keys]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    args = parse_args()
    if args.discussion_rounds < 1:
        raise SystemExit("--discussion-rounds must be at least 1.")
    user_task = read_prompt(args).strip()
    if not user_task and not args.dry_run:
        raise SystemExit("Prompt is empty.")

    runtime = prepare_runtime(args)
    selected = runtime["selected"]
    synthesizers = runtime["synthesizers"]
    skipped = runtime["skipped"]

    if args.dry_run:
        print(json.dumps(dry_run_output(skill_name=SKILL_NAME, selected=selected, skipped=skipped, synthesizers=synthesizers, prompt=user_task, discussion_rounds=args.discussion_rounds), ensure_ascii=False, indent=2))
        return 0

    if not selected:
        raise SystemExit("No usable respondent models. Check --models, API keys, and LiteLLM /v1/models.")
    if not args.no_synthesis and not synthesizers:
        eprint("[discussion] no usable synthesizer; the run will return discussion answers only")

    run_id = local_run_id()
    out_dir = Path(args.out_dir) if args.out_dir else codex_home() / "tmp" / "multi-model-discussion" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "task.txt").write_text(user_task, encoding="utf-8")
    prices = load_price_config(args.price_config)
    started = time.monotonic()

    eprint(f"[discussion] output directory: {out_dir}")
    eprint(f"[discussion] launching initial calls for {len(selected)} models")
    initial_messages_by_member = {member["key"]: initial_messages(user_task) for member in selected}
    initial_results = run_round(members=selected, messages_by_member=initial_messages_by_member, out_dir=out_dir, output_prefix="initial", args=args, prices=prices)

    active_members = active_members_from_results(selected, initial_results)
    eprint(f"[discussion] initial success: {len(active_members)}/{len(selected)}")
    discussion_rounds: List[List[Dict[str, Any]]] = []
    previous_round: List[Dict[str, Any]] = []
    run_record: Dict[str, Any] = {
        "run_id": run_id,
        "mode": "direct-litellm-chat-completions-api-with-discussion",
        "started_at": utc_now_iso(),
        "task_path": str(out_dir / "task.txt"),
        "output_dir": str(out_dir),
        "models_requested": parse_csv(args.models) or [item["model"] for item in PANEL],
        "models_used": [item["model"] for item in selected],
        "models_skipped": format_skipped(skipped),
        "panel": selected,
        "initial_results": initial_results,
        "discussion_rounds": discussion_rounds,
    }

    stage_cost = aggregate_usage_and_cost(run_record)
    if args.max_cost_usd is not None and stage_cost["estimated_cost_usd_known"] > args.max_cost_usd:
        run_record["status"] = "partial_success"
        final_content = manual_fallback_answer("Cost cap reached after initial answers", initial_results, args.max_chars_per_response)
        finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
        print(final_content)
        return 4

    for round_number in range(1, args.discussion_rounds + 1):
        if not active_members:
            eprint("[discussion] no active models left for discussion")
            break
        eprint(f"[discussion] launching discussion round {round_number} for {len(active_members)} models")
        messages_by_member = {
            member["key"]: discussion_messages(
                user_task,
                member,
                initial_results,
                previous_round,
                round_number,
                args.max_chars_per_response,
            )
            for member in active_members
        }
        round_results = run_round(members=active_members, messages_by_member=messages_by_member, out_dir=out_dir, output_prefix=f"discussion{round_number}", args=args, prices=prices)
        discussion_rounds.append(round_results)
        previous_round = round_results
        active_members = active_members_from_results(active_members, round_results)
        stage_cost = aggregate_usage_and_cost(run_record)
        if args.max_cost_usd is not None and stage_cost["estimated_cost_usd_known"] > args.max_cost_usd:
            run_record["status"] = "partial_success"
            final_content = manual_fallback_answer("Cost cap reached during discussion", round_results, args.max_chars_per_response)
            finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
            print(final_content)
            return 4

    successful_final_round = successful(discussion_rounds[-1]) if discussion_rounds else successful(initial_results)
    if not successful_final_round:
        run_record["status"] = "failed"
        final_content = "All respondent models failed before synthesis. See report.md and errors/ for details."
        finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
        print(final_content)
        return 2

    if args.no_synthesis or not synthesizers:
        run_record["status"] = run_status(discussion_rounds[-1] if discussion_rounds else initial_results)
        final_content = manual_fallback_answer("Synthesis", successful_final_round, args.max_chars_per_response)
        finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
        print(final_content)
        return 0

    synthesis = run_synthesis(
        synthesizers,
        synthesis_messages(user_task, initial_results, discussion_rounds, args.max_chars_per_response),
        out_dir,
        args,
        prices,
    )
    run_record["synthesis"] = synthesis["final"]
    run_record["synthesis_attempts"] = synthesis["attempts"]
    final = synthesis["final"]

    if final.get("status") == "success":
        run_record["status"] = "partial_success" if len(successful(initial_results)) < len(selected) else "success"
        final_content = str(final.get("content") or "").strip()
    else:
        run_record["status"] = "partial_success"
        final_content = manual_fallback_answer("Synthesis", successful_final_round, args.max_chars_per_response)

    metadata = finalize_run(skill_name=SKILL_NAME, run_record=run_record, output_dir=out_dir, started_monotonic=started, final_content=final_content)
    if check_cost_cap(metadata, args.max_cost_usd):
        eprint(f"[discussion] known estimated cost exceeded --max-cost-usd: {metadata['estimated_cost_usd_known']}")
    print(final_content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
