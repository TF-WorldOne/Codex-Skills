---
name: multi-model-discussion
description: Run a five-model panel with an explicit discussion round before final synthesis. Use when the user asks multiple AI models to give independent opinions, then debate, discuss, critique, reconsider, or refine each other's views before GPT 5.5 Pro produces the final output.
---

# Multi-Model Discussion

Use this skill to send one task to five model APIs, collect independent first answers, run one or more discussion/revision rounds, and have GPT 5.5 Pro synthesize the final result.

## Panel

Use these LiteLLM API model routes and roles:

- `gpt-5.5`: GPT 5.5 Pro respondent.
- `opus-4.8-max`: Claude Opus 4.8 at max reasoning effort.
- `deepseek-v4-pro`: DeepSeek V4 Pro respondent.
- `glm-5.2`: GLM 5.2 respondent.
- `gemini-3.1-pro-deep-think`: Gemini 3.1 Pro Preview with high thinking level for Deep Think behavior.
- `gpt-5.5`: GPT 5.5 Pro final synthesizer after the discussion round.

## Workflow

Run the helper script from the plugin root:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "USER TASK HERE"
```

For long prompts:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt-file "C:\path\to\task.txt"
```

The script starts the local LiteLLM router if needed, calls all five respondent model APIs in parallel, then shows the first-round answers to all five models for a discussion/revision round. It saves all raw outputs under `%USERPROFILE%\.codex\tmp\multi-model-discussion\`, then calls GPT 5.5 once to synthesize.

Use `--discussion-rounds 2` or higher when the user explicitly wants deeper debate. Use the default single discussion round for normal use.

## Output Rules

- Preserve the initial independent answers separately from discussion outputs.
- Make the discussion round critique, compare, correct, and refine the first answers.
- Do not let models roleplay each other; each model should revise its own view after seeing the others.
- Return the GPT 5.5 synthesis as the main answer.
- Mention failed models only when the script reports a failure.
- Use the same language as the user's task unless the task asks otherwise.

## Failure Handling

If one model fails in either round, continue with the available successful answers. If GPT 5.5 synthesis fails, report the saved output directory and summarize the available final discussion outputs manually.
