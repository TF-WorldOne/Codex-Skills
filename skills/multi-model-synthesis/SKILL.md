---
name: multi-model-synthesis
description: Run a selectable multi-model independent answer panel and synthesize the results. Use when the user asks for multiple top models, a model council, parallel opinions, GPT 5.5 Pro plus Opus/DeepSeek/GLM/Gemini comparison, or a single final answer produced from independent model outputs without a debate/discussion round. Supports model selection, available-model filtering, partial success, retries, cost/token logging, and configurable synthesizers.
---

# TawabaranPro - Synth Model

Use this skill to send one user task to selected model APIs in parallel, collect independent answers, and have a configurable synthesizer produce the final synthesis.

## Panel

Use these LiteLLM API model routes and roles:

- `gpt-5.5`: GPT 5.5 Pro respondent.
- `opus-4.8-max`: Claude Opus 4.8 at max reasoning effort.
- `deepseek-v4-pro`: DeepSeek V4 Pro respondent.
- `glm-5.2`: GLM 5.2 respondent.
- `gemini-3.1-pro-deep-think`: Gemini 3.1 Pro Preview with high thinking level for Deep Think behavior.
- default synthesizer: `gpt-5.5`, overridable with `--synthesizer`.

## Workflow

Run the helper script instead of manually launching each model:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "USER TASK HERE"
```

Choose models and synthesizer:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "USER TASK HERE" --models opus-4.8-max,gemini-3.1-pro-deep-think --synthesizer opus-4.8-max
```

For long prompts or prompts with quotes, write the task to a temporary text file and run:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt-file "C:\path\to\task.txt"
```

The script starts the local LiteLLM router if needed, checks `/v1/models`, filters out models missing local API keys or LiteLLM registrations, calls usable respondent model APIs in parallel, saves raw outputs under `%USERPROFILE%\.codex\tmp\multi-model-synthesis\`, then calls the selected synthesizer with fallback synthesizers if needed. Use `CODEX_MULTI_MODEL_ROUTER_SCRIPT` or `CODEX_MULTI_MODEL_LITELLM_CONFIG` to override the bundled router script or LiteLLM config.

Use `--dry-run` to inspect planned models without chat completions. Use `--retries`, `--timeout`, `--allow-partial`, `--synthesizer-fallbacks`, `--price-config`, and `--max-cost-usd` for reliability and cost control.

Run artifacts include `final.md`, `report.md`, `metadata.json`, `run.json`, `models/*.md`, `raw/*.response.json`, and `errors/*.log`.

## Output Rules

- Do not add a debate, critique, or second discussion round.
- Preserve each model answer as an independent source for the synthesis.
- Return the selected synthesizer's final answer as the main answer.
- Mention any model that failed only when the script reports a failure.
- Use the same language as the user's task unless the task asks otherwise.

## Failure Handling

If one respondent fails, continue with available successful answers by default. If the selected synthesizer fails, try fallback synthesizers. If all synthesizers fail, report the saved output directory and return the successful respondent answers manually.
