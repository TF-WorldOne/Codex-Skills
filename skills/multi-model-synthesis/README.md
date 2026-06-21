# TawabaranPro - Synth Model

## 日本語

`multi-model-synthesis` は、1つの課題を5つのモデルAPIへ同時に投げ、各モデルの独立回答を集めたあと、GPT 5.5 Pro が最終回答をまとめる Codex Skill です。

このスキルは、ディスカッションや反論ラウンドを挟まず、複数モデルの初回回答からすぐに結論を出したいときに使います。

現在は、利用可能なAPIキーと LiteLLM `/v1/models` を確認し、使えるモデルだけで実行できます。統括モデルも `--synthesizer` で変更できます。

### 使用モデル

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

### 何に向いているか

- すばやく複数AIの見解を集めたい
- 最終的な結論だけ知りたい
- 比較、推薦、アイデア出し、意思決定の下調べをしたい
- ディスカッションより速度を優先したい

### 実行例

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "日本で最も美味しいと思われるうなぎ屋さんはどこですか？"
```

使うモデルと統括モデルを指定する例:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "..." --models opus-4.8-max,gemini-3.1-pro-deep-think --synthesizer opus-4.8-max
```

API呼び出しなしで構成だけ確認する例:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --dry-run --skip-model-check --models deepseek-v4-pro,gemini-3.1-pro-deep-think
```

長い課題文はテキストファイルに保存して実行できます。

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt-file "C:\path\to\task.txt"
```

### 出力

- 5モデルの独立回答
- 各モデルの生レスポンス
- 選択した統括モデルによる最終統合回答
- `metadata.json` にモデル別成功/失敗、トークン使用量、推定コスト
- `report.md` と `final.md`

実行結果は通常、次の場所に保存されます。

```text
%USERPROFILE%\.codex\tmp\multi-model-synthesis\
```

主なファイル:

- `final.md`: 最終回答
- `report.md`: 人間向け実行レポート
- `metadata.json`: 実行ID、使用モデル、成功/失敗、トークン、推定コスト
- `run.json`: 後処理/API連携向けの全部入りデータ
- `models/*.md`: モデル別回答
- `raw/*.response.json`: API生レスポンス
- `errors/*.log`: 失敗ログ

価格推定を使う場合は `examples/model-prices.example.json` をコピーして実価格を入れ、`--price-config` で指定してください。

### 必要な環境変数

```powershell
$env:OPENAI_API_KEY = "..."
$env:ANTHROPIC_API_KEY = "..."
$env:DEEPSEEK_API_KEY = "..."
$env:ZAI_API_KEY = "..."
$env:GEMINI_API_KEY = "..."
```

APIキーはリポジトリに含めないでください。

### Discussion版との違い

`multi-model-synthesis` は、各モデルの初回回答をそのまま GPT 5.5 Pro がまとめます。

モデル同士に他モデルの回答を読ませて再考させたい場合は、`multi-model-discussion` を使います。

---

## English

`multi-model-synthesis` is a Codex Skill that sends one task to five model APIs in parallel, collects independent answers, and asks GPT 5.5 Pro to produce the final synthesized answer.

Use this skill when you want a fast final answer from multiple independent model perspectives without a debate or revision round.

It now filters by available API keys and LiteLLM `/v1/models`, supports selectable models, and allows a configurable synthesizer with fallbacks.

### Models

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

### Best For

- Quickly collecting multiple AI opinions
- Getting only the final conclusion
- Comparisons, recommendations, ideation, and decision research
- Prioritizing speed over cross-model discussion

### Usage

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "What is the best unagi restaurant in Japan?"
```

Select models and synthesizer:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt "..." --models opus-4.8-max,gemini-3.1-pro-deep-think --synthesizer opus-4.8-max
```

Inspect the planned run without chat completions:

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --dry-run --skip-model-check --models deepseek-v4-pro,gemini-3.1-pro-deep-think
```

For long prompts, save the task to a text file.

```powershell
py ".\skills\multi-model-synthesis\scripts\run_panel.py" --prompt-file "C:\path\to\task.txt"
```

### Output

- Independent answers from five models
- Raw model responses
- Final synthesis from the selected synthesizer
- Token usage, estimated cost, success/failure metadata
- `report.md` and `final.md`

Run artifacts are usually saved under:

```text
%USERPROFILE%\.codex\tmp\multi-model-synthesis\
```

Main files:

- `final.md`: final answer
- `report.md`: human-readable run report
- `metadata.json`: run id, models used/skipped, status, tokens, estimated cost
- `run.json`: complete machine-readable record
- `models/*.md`: model answers
- `raw/*.response.json`: raw API responses
- `errors/*.log`: failure logs

For cost estimates, copy `examples/model-prices.example.json`, enter current prices, and pass it with `--price-config`.

### Required Environment Variables

```powershell
$env:OPENAI_API_KEY = "..."
$env:ANTHROPIC_API_KEY = "..."
$env:DEEPSEEK_API_KEY = "..."
$env:ZAI_API_KEY = "..."
$env:GEMINI_API_KEY = "..."
```

Do not commit API keys to this repository.

### Difference From Discussion

`multi-model-synthesis` synthesizes the models' first independent answers immediately.

Use `multi-model-discussion` when you want models to read each other's answers, critique them, revise their own positions, and then produce a final synthesis.
