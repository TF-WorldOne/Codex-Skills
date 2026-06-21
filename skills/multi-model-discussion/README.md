# TawabaranPro - Discussion Model

## 日本語

`multi-model-discussion` は、1つの課題を5つのモデルAPIへ同時に投げ、まず各モデルに独立回答させたあと、その回答を全モデルに共有して再考・批判・補足させ、最後に GPT 5.5 Pro が総括する Codex Skill です。

このスキルは、単なる多数決ではなく、モデル同士の視点差を使って結論を強くしたいときに使います。

現在は、利用可能なAPIキーと LiteLLM `/v1/models` を確認し、使えるモデルだけで実行できます。統括モデルも `--synthesizer` で変更できます。

### 使用モデル

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

### 処理の流れ

1. 5モデルが同じ課題に独立回答する
2. すべての初回回答を各モデルに共有する
3. 各モデルが他モデルの回答を見て、弱点、見落とし、修正点を検討する
4. 各モデルが改訂意見を出す
5. GPT 5.5 Pro が最終回答を統合する

### 何に向いているか

- 重要な意思決定
- リスク分析
- 事業案、投資案、設計方針の検討
- 推薦やランキングで根拠を強めたい場合
- 1回の回答では見落としが怖い課題

### 実行例

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "この事業案のリスクと勝ち筋を検討してください。"
```

使うモデルと統括モデルを指定する例:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "..." --models opus-4.8-max,gemini-3.1-pro-deep-think --synthesizer opus-4.8-max
```

API呼び出しなしで構成だけ確認する例:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --dry-run --skip-model-check --models deepseek-v4-pro,gemini-3.1-pro-deep-think --discussion-rounds 2
```

長い課題文はテキストファイルに保存して実行できます。

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt-file "C:\path\to\task.txt"
```

議論ラウンドを増やす場合:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "この設計方針を評価してください。" --discussion-rounds 2
```

### 出力

- 5モデルの初回独立回答
- ディスカッション後の各モデルの改訂回答
- 各モデルの生レスポンス
- 選択した統括モデルによる最終統合回答
- `metadata.json` にモデル別成功/失敗、トークン使用量、推定コスト
- `report.md` と `final.md`

実行結果は通常、次の場所に保存されます。

```text
%USERPROFILE%\.codex\tmp\multi-model-discussion\
```

主なファイル:

- `final.md`: 最終回答
- `report.md`: 人間向け実行レポート
- `metadata.json`: 実行ID、使用モデル、成功/失敗、トークン、推定コスト
- `run.json`: 後処理/API連携向けの全部入りデータ
- `models/*.md`: 初回回答・議論回答・統括回答
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

### Synthesis版との違い

`multi-model-discussion` は、初回回答のあとにモデル同士の回答を読ませる再考ラウンドがあります。

ディスカッションなしで速く結論だけ出したい場合は、`multi-model-synthesis` を使います。

---

## English

`multi-model-discussion` is a Codex Skill that sends one task to five model APIs in parallel, collects independent first answers, shares those answers back to the full panel for critique and revision, and then asks GPT 5.5 Pro to produce the final synthesis.

Use this skill when you want stronger conclusions through cross-model review rather than a simple one-pass answer.

It now filters by available API keys and LiteLLM `/v1/models`, supports selectable models, and allows a configurable synthesizer with fallbacks.

### Models

- GPT 5.5 Pro
- Claude Opus 4.8 Max
- DeepSeek V4 Pro
- GLM 5.2
- Gemini 3.1 Pro Deep Think

### Flow

1. Five models answer the same task independently
2. All first-round answers are shared with every model
3. Each model reviews weaknesses, omissions, and corrections
4. Each model submits a revised position
5. GPT 5.5 Pro synthesizes the final answer

### Best For

- Important decisions
- Risk analysis
- Business, investment, and architecture reviews
- Recommendations or rankings that need stronger justification
- Tasks where a one-pass answer may miss important issues

### Usage

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "Evaluate the risks and strongest path for this business idea."
```

Select models and synthesizer:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "..." --models opus-4.8-max,gemini-3.1-pro-deep-think --synthesizer opus-4.8-max
```

Inspect the planned run without chat completions:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --dry-run --skip-model-check --models deepseek-v4-pro,gemini-3.1-pro-deep-think --discussion-rounds 2
```

For long prompts, save the task to a text file.

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt-file "C:\path\to\task.txt"
```

To increase discussion depth:

```powershell
py ".\skills\multi-model-discussion\scripts\run_discussion.py" --prompt "Review this architecture decision." --discussion-rounds 2
```

### Output

- First independent answers from five models
- Revised answers after the discussion round
- Raw model responses
- Final synthesis from the selected synthesizer
- Token usage, estimated cost, success/failure metadata
- `report.md` and `final.md`

Run artifacts are usually saved under:

```text
%USERPROFILE%\.codex\tmp\multi-model-discussion\
```

Main files:

- `final.md`: final answer
- `report.md`: human-readable run report
- `metadata.json`: run id, models used/skipped, status, tokens, estimated cost
- `run.json`: complete machine-readable record
- `models/*.md`: initial, discussion, and synthesis answers
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

### Difference From Synthesis

`multi-model-discussion` includes a revision round where each model reads the other models' answers and updates its own position.

Use `multi-model-synthesis` when you want a faster final answer without cross-model discussion.
