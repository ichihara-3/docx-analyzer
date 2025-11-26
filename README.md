# docx-analyzer

DOCX を解析して、本文・段落構造・追跡履歴・コメントを JSON 化し、LLM（Gemini / OpenAI）に渡せる形にするための実験リポジトリです。
Web UI を使って、ブラウザ上で解析結果の確認や LLM レビュー、コメント付き DOCX のダウンロードが可能です。

## セットアップ

```bash
uv sync
```

LLM レビューを実行するには、使用するモデルに応じて環境変数を設定してください。

```bash
cp .env.example .env
# Gemini を使う場合
echo "GOOGLE_API_KEY=xxxx" >> .env
```

## 使い方

### Web UI（推奨）

ブラウザで直感的に操作できます。

```bash
uv run docx-web
```

`http://127.0.0.1:8000` にアクセスしてください。

**機能:**
- **解析 & レビュー**: DOCX をアップロードして、解析結果と LLM によるレビューを表示します。
- **コメント埋め込み**: レビュー結果を元の DOCX にコメントとして埋め込み、ダウンロードできます。
- **モデル選択**: `gemini-2.5-flash`, `gpt-4o` など、複数のモデルを切り替えて試せます。

### CLI（コマンドライン）

#### 解析のみ

```bash
uv run docx-analyze sample.docx
```

段落ごとに以下のようなデータを得ます。

```json
{
  "path": "sample.docx",
  "paragraphs": [
    {
      "index": 0,
      "text": "現在の本文",
      "list": {"num_id": "1", "ilvl": "0"},
      "events": [
        {"kind": "add", "text": "新規追加", "author": "Alice", "date": "..."},
        {"kind": "delete", "text": "削除された文言", "author": "Bob", "date": "..."},
        {"kind": "comment", "text": "対象範囲", "comment_id": "1", "comment_text": "修正理由"}
      ]
    }
  ]
}
```

#### 解析＋LLM レビュー

```bash
uv run docx-analyze sample.docx --review --prompt prompt.txt
```

- `--prompt` でカスタムプロンプトを渡せます（省略時は日本語の契約レビュー用プロンプトで応答）。
- `--model` でモデルを指定できます（例: `gemini-1.5-pro`, `gpt-4o`）。

## 実装メモ

- DOCX は ZIP として展開し、`word/document.xml` を lxml で解析しています。
- 追跡履歴: `w:ins`/`w:del`/`w:moveFrom`/`w:moveTo` を `events` に格納。`text` は該当ブロックの `w:t` を連結。
- コメント: `word/comments.xml` を読み込み、`commentRangeStart`/`commentRangeEnd` 間の本文を `text` に、コメント本文を `comment_text` に格納。
- 段落構造: 段落インデックスと箇条書きの `num_id`/`ilvl` を保持（番号体系の解決は未実装）。

## 今後の拡張アイデア

- 表・脚注・ヘッダ/フッタの解析を追加。
- 番号付きリストを `abstractNum` 定義に基づき人間可読な形式に復元。
- 追跡履歴の差分（誰がいつ何をどの状態から変更したか）をより詳細に復元。
- 生成した JSON からレビュー用サマリを作る前処理（重要段落の抽出、変更の重要度スコアリングなど）。
