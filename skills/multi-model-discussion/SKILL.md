---
name: multi-model-discussion
description: Run a selectable multi-model panel with explicit discussion rounds before final synthesis. Use when the user asks multiple AI models to give independent opinions, then debate, discuss, critique, reconsider, or refine each other's views before final output. Supports model selection, available-model filtering, partial success, retries, cost/token logging, and configurable synthesizers.
---

# TawabaranPro - Discussion Model

Use this skill to send one task to selected model APIs, collect independent first answers, run one or more discussion/revision rounds, and have a configurable synthesizer produce the final result.

## Panel

Use these LiteLLM API model routes and roles:

- `gpt-5.5`: GPT 5.5 Pro respondent.
- `opus-4.8-max`: Claude Opus 4.8 at max reasoning effort.
- `deepseek-v4-pro`: DeepSeek V4 Pro respondent.
- `glm-5.2`: GLM 5.2 respondent.
- `gemini-3.1-pro-deep-think`: Gemini 3.1 Pro Preview with high thinking level for Deep Think behavior.
- default synthesizer: `gpt-5.5`, overridable with `--synthesizer`.

## Workflow

Run the helper script from the plugin root:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "USER TASK HERE"
```

Choose models and synthesizer:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "USER TASK HERE" --models opus-4.8-max,gemini-3.1-pro-deep-think --synthesizer opus-4.8-max
```

For long prompts:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt-file "C:\path\to\task.txt"
```

The script starts the local LiteLLM router if needed, checks `/v1/models`, filters out models missing local API keys or LiteLLM registrations, calls usable respondent model APIs in parallel, then shows successful first-round answers to active models for discussion/revision rounds. It saves all raw outputs under `%USERPROFILE%\.codex\tmp\multi-model-discussion\`, then calls the selected synthesizer with fallback synthesizers if needed.

Use `--discussion-rounds 2` or higher when the user explicitly wants deeper debate. Use the default single discussion round for normal use.

Use `--dry-run` to inspect planned models without chat completions. Use `--retries`, `--timeout`, `--allow-partial`, `--synthesizer-fallbacks`, `--price-config`, and `--max-cost-usd` for reliability and cost control.

Run artifacts include `final.md`, `report.md`, `metadata.json`, `run.json`, `models/*.md`, `raw/*.response.json`, and `errors/*.log`.

## Output Rules

- Preserve the initial independent answers separately from discussion outputs.
- Make the discussion round critique, compare, correct, and refine the first answers using: agreements, disagreements, missing points, corrections, final recommendation, and confidence.
- Do not let models roleplay each other; each model should revise its own view after seeing the others.
- Return the selected synthesizer's final answer as the main answer.
- Mention failed models only when the script reports a failure.
- Use the same language as the user's task unless the task asks otherwise.

## Failure Handling

If one model fails in either round, continue with the available successful answers by default. If the selected synthesizer fails, try fallback synthesizers. If all synthesizers fail, report the saved output directory and return the successful final discussion outputs manually.
