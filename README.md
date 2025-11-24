# docx-analyzer

DOCX を解析して、本文・段落構造・追跡履歴・コメントを JSON 化し、LLM（Gemini）に渡せる形にするための実験リポジトリです。

## セットアップ

```
uv sync
```

環境変数 `GOOGLE_API_KEY` を設定すると LLM レビューを実行できます。

```
cp .env.example .env
echo "GOOGLE_API_KEY=xxxx" >> .env
```

## 使い方

### 解析のみ

```
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

### 解析＋Gemini でのレビュー

```
uv run docx-analyze sample.docx --review --prompt prompt.txt
```

- `--prompt` でカスタムプロンプトを渡せます（省略時は日本語の契約レビュー用プロンプトで応答）。
- `--model` で `gemini-1.5-pro-002` など別モデルも指定できます。

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
