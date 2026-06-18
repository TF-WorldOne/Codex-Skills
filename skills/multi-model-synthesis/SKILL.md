---
name: multi-model-synthesis
description: Run a five-model independent answer panel and synthesize the results. Use when the user asks for multiple top models, a model council, parallel opinions, GPT 5.5 Pro plus Opus/DeepSeek/GLM/Gemini comparison, or a single final answer produced from independent model outputs without a debate/discussion round.
---

# Multi-Model Synthesis

Use this skill to send one user task to five model APIs in parallel, collect independent answers, and have GPT 5.5 Pro produce the final synthesis.

## Panel

Use these LiteLLM API model routes and roles:

- `gpt-5.5`: GPT 5.5 Pro respondent.
- `opus-4.8-max`: Claude Opus 4.8 at max reasoning effort.
- `deepseek-v4-pro`: DeepSeek V4 Pro respondent.
- `glm-5.2`: GLM 5.2 respondent.
- `gemini-3.1-pro-deep-think`: Gemini 3.1 Pro Preview with high thinking level for Deep Think behavior.
- `gpt-5.5`: GPT 5.5 Pro synthesizer after the respondent round finishes.

## Workflow

Run the helper script instead of manually launching each model:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "USER TASK HERE"
```

For long prompts or prompts with quotes, write the task to a temporary text file and run:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt-file "C:\path\to\task.txt"
```

The script starts the local LiteLLM router if needed, calls all five respondent model APIs in parallel through `http://127.0.0.1:4141/v1/chat/completions`, saves raw outputs under `%USERPROFILE%\.codex\tmp\multi-model-synthesis\`, then calls the GPT 5.5 API once to synthesize. Use `CODEX_MULTI_MODEL_ROUTER_SCRIPT` or `CODEX_MULTI_MODEL_LITELLM_CONFIG` to override the bundled router script or LiteLLM config.

## Output Rules

- Do not add a debate, critique, or second discussion round.
- Preserve each model answer as an independent source for the synthesis.
- Return the GPT 5.5 synthesis as the main answer.
- Mention any model that failed only when the script reports a failure.
- Use the same language as the user's task unless the task asks otherwise.

## Failure Handling

If one respondent fails, synthesize from the available successful answers and clearly identify the failed respondent. If GPT 5.5 synthesis fails, report the saved output directory and summarize the respondent answers manually.
