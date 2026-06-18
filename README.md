# Codex Skills

## 日本語

このリポジトリは、Codexで使う個人・チーム向けSkill/Plugin集です。現在は、複数のAIモデルを同時に使って回答を作る2つのスキルを収録しています。

### 収録スキル

#### 1. Multi-Model Synthesis

`multi-model-synthesis` は、1つの課題を5つのモデルAPIへ同時に投げ、各モデルの独立回答をGPT 5.5 Proがすぐに総括するスキルです。

使うモデル:

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

特徴:

- 5モデルへの同時API呼び出し
- 各モデルの独立回答を保存
- ディスカッションなしでGPT 5.5 Proが最終統合
- 結論だけを素早く見たい用途向け

実行例:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "日本で最も美味しいと思われるうなぎ屋さんはどこですか？"
```

#### 2. Multi-Model Discussion

`multi-model-discussion` は、1つの課題を5つのモデルAPIへ同時に投げたあと、各モデルに他モデルの回答を読ませて反論・補足・再評価させ、最後にGPT 5.5 Proが総括するスキルです。

流れ:

1. 5モデルが独立回答する
2. その回答を全モデルに共有する
3. 各モデルが批判・補足・再評価する
4. GPT 5.5 Proが最終結論を作る

特徴:

- 初回回答と議論ラウンドを分けて保存
- モデル同士の観点差を使って結論を強化
- `--discussion-rounds` で議論ラウンド数を増やせる
- 重要判断、比較検討、リスク評価向け

実行例:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "この事業案のリスクと勝ち筋を検討してください。"
```

議論ラウンドを2回にする例:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "この設計方針を評価してください。" --discussion-rounds 2
```

### 必要なもの

- Codex
- Python 3
- PowerShell
- LiteLLM
- 各プロバイダーのAPIキー

必要な環境変数:

```powershell
$env:OPENAI_API_KEY = "..."
$env:ANTHROPIC_API_KEY = "..."
$env:DEEPSEEK_API_KEY = "..."
$env:ZAI_API_KEY = "..."
$env:GEMINI_API_KEY = "..."
```

APIキーはこのリポジトリに含めないでください。利用者が自分の環境変数として設定します。

### LiteLLM設定

デフォルトでは `examples/litellm-config.example.yaml` を使ってLiteLLMルーターを起動します。別の設定ファイルを使う場合は `CODEX_MULTI_MODEL_LITELLM_CONFIG` を指定してください。

```powershell
$env:CODEX_MULTI_MODEL_LITELLM_CONFIG = "C:\path\to\litellm.yaml"
```

既存のルーター起動スクリプトを使う場合は `CODEX_MULTI_MODEL_ROUTER_SCRIPT` を指定できます。

```powershell
$env:CODEX_MULTI_MODEL_ROUTER_SCRIPT = "C:\path\to\start-router.ps1"
```

### 注意

このPluginは、指定されたモデルIDが利用者のアカウント/APIキーで使えることを前提にしています。モデル名やAPI提供状況は変わる可能性があるため、必要に応じて `examples/litellm-config.example.yaml` を編集してください。

---

## English

This repository contains reusable Codex Skills/Plugin assets for personal or team workflows. It currently includes two skills that use multiple AI model APIs to produce stronger answers.

### Included Skills

#### 1. Multi-Model Synthesis

`multi-model-synthesis` sends one task to five model APIs in parallel, collects independent answers, and asks GPT 5.5 Pro to synthesize the final answer immediately.

Models:

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

Capabilities:

- Parallel API calls to five models
- Saved independent model responses
- Final synthesis by GPT 5.5 Pro with no discussion round
- Best for quick final conclusions from multiple independent views

Usage:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "What is the best unagi restaurant in Japan?"
```

#### 2. Multi-Model Discussion

`multi-model-discussion` sends one task to five model APIs in parallel, then shows the first-round answers to all models so they can critique, revise, and refine their positions. GPT 5.5 Pro then produces the final synthesis.

Flow:

1. Five models answer independently
2. Their answers are shared with the full panel
3. Each model critiques and revises its own position
4. GPT 5.5 Pro writes the final synthesis

Capabilities:

- Separate saved initial answers and discussion rounds
- Stronger conclusions through cross-model critique
- Configurable discussion depth with `--discussion-rounds`
- Best for important decisions, comparisons, and risk analysis

Usage:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "Evaluate this product strategy."
```

Two discussion rounds:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "Review this architecture decision." --discussion-rounds 2
```

### Requirements

- Codex
- Python 3
- PowerShell
- LiteLLM
- API keys for the model providers

Required environment variables:

```powershell
$env:OPENAI_API_KEY = "..."
$env:ANTHROPIC_API_KEY = "..."
$env:DEEPSEEK_API_KEY = "..."
$env:ZAI_API_KEY = "..."
$env:GEMINI_API_KEY = "..."
```

Do not commit API keys to this repository. Each user should configure their own environment variables.

### LiteLLM Configuration

By default, the scripts start LiteLLM with `examples/litellm-config.example.yaml`. To use a custom config, set `CODEX_MULTI_MODEL_LITELLM_CONFIG`.

```powershell
$env:CODEX_MULTI_MODEL_LITELLM_CONFIG = "C:\path\to\litellm.yaml"
```

To use an existing router startup script, set `CODEX_MULTI_MODEL_ROUTER_SCRIPT`.

```powershell
$env:CODEX_MULTI_MODEL_ROUTER_SCRIPT = "C:\path\to\start-router.ps1"
```

### Notes

This plugin assumes the named model IDs are available to the user's accounts and API keys. If providers change model IDs or availability, update `examples/litellm-config.example.yaml`.
