# Multi-Model Synthesis for Codex

## 日本語

**Multi-Model Synthesis** は、Codexで1つの課題を複数の最上位モデルに同時に投げ、最後にGPT 5.5 Proで総括するためのCodex Skill/Pluginです。

このスキルは次の5モデルに独立して回答させます。

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

その後、各モデルの回答をGPT 5.5 Proに渡し、議論ラウンドを挟まずに最終結論だけを生成します。複数AIの意見を一気に取り、最後のまとめだけ見たい用途に向いています。

### 何ができるか

- 5モデルへの同時API呼び出し
- 各モデルの独立回答の保存
- GPT 5.5 Proによる最終統合
- 失敗したモデルがあっても、成功した回答から継続
- LiteLLM経由のOpenAI互換APIルーティング

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

### 使い方

Pluginルートで以下を実行します。

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "日本で最も美味しいと思われるうなぎ屋さんはどこですか？"
```

長い課題はテキストファイルにして渡せます。

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt-file ".\task.txt"
```

デフォルトでは `examples/litellm-config.example.yaml` を使ってLiteLLMルーターを起動します。別の設定ファイルを使う場合は `CODEX_MULTI_MODEL_LITELLM_CONFIG` を指定してください。

```powershell
$env:CODEX_MULTI_MODEL_LITELLM_CONFIG = "C:\path\to\litellm.yaml"
```

### 注意

このPluginは、指定されたモデルIDが利用者のアカウント/APIキーで使えることを前提にしています。モデル名やAPI提供状況は変わる可能性があるため、必要に応じて `examples/litellm-config.example.yaml` を編集してください。

---

## English

**Multi-Model Synthesis** is a Codex Skill/Plugin that sends one task to multiple top-tier model APIs in parallel, then asks GPT 5.5 Pro to synthesize the final answer.

The panel uses:

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

Each model answers independently. There is no debate or discussion round. GPT 5.5 Pro receives the independent answers and produces the final output.

### Capabilities

- Parallel API calls to five models
- Saved raw responses for each model
- Final synthesis by GPT 5.5 Pro
- Partial-failure handling when one model fails
- OpenAI-compatible routing through LiteLLM

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

### Usage

From the plugin root:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "What is the best unagi restaurant in Japan?"
```

For longer prompts:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt-file ".\task.txt"
```

By default, the script starts LiteLLM with `examples/litellm-config.example.yaml`. To use a custom config, set `CODEX_MULTI_MODEL_LITELLM_CONFIG`.

```powershell
$env:CODEX_MULTI_MODEL_LITELLM_CONFIG = "C:\path\to\litellm.yaml"
```

### Notes

This plugin assumes the named model IDs are available to the user's accounts and API keys. If providers change model IDs or availability, update `examples/litellm-config.example.yaml`.
