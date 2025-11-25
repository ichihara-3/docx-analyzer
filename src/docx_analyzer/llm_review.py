from __future__ import annotations

import json
import os
from typing import Dict, Iterable, Optional

import google.generativeai as genai
from dotenv import load_dotenv

from .parser import DocumentAnalysis


class LLMReviewer:
    """Very small wrapper around Gemini to review a parsed DOCX."""

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        system_instruction: Optional[str] = None,
    ):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=api_key)
        self.model_name = model
        self.system_instruction = system_instruction or SYSTEM_INSTRUCTION

    def review(self, analysis: DocumentAnalysis, user_instruction: Optional[str] = None) -> str:
        """Send the analysis and a reviewer prompt to the LLM, return plain text."""
        instruction = user_instruction or DEFAULT_USER_INSTRUCTION
        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=self.system_instruction,
        )
        content = build_llm_payload(analysis, instruction)
        response = model.generate_content(content)
        return response.text or ""


DEFAULT_SYSTEM_PROMPT = """\
あなたは契約レビュー担当者です。以下の DOCX 解析結果を読み、日本語で簡潔なレビューコメントを箇条書きで出力してください。

## 入力データの構造

入力は以下の構造を持つJSONです：

```json
{
  "path": "ファイルパス",
  "paragraphs": [
    {
      "index": 段落番号（0から始まる）,
      "text": "段落の最終的なテキスト（追跡変更を反映済み）",
      "list": {
        "num_id": "リスト番号ID（リスト項目の場合）",
        "ilvl": "インデントレベル（リスト項目の場合）"
      },
      "events": [
        {
          "kind": "イベント種別",
          "text": "変更対象のテキスト",
          "author": "変更者名",
          "date": "変更日時（ISO 8601形式）",
          "comment_id": "コメントID（コメントの場合）",
          "comment_text": "コメント本文（コメントの場合）"
        }
      ]
    }
  ]
}
```

## フィールドの意味

- **paragraphs**: 文書内の全段落のリスト
- **index**: 段落の位置（参照時に使用）
- **text**: 追跡変更を適用した後の最終テキスト（削除は除外、追加は含む）
- **list**: リスト項目の場合、番号とインデントレベルを含む
- **events**: この段落で発生した変更イベント（時系列順にソート済み）

## イベント種別（kind）

- **add**: テキストの追加（挿入）
- **delete**: テキストの削除
- **move_from**: テキストの移動元
- **move_to**: テキストの移動先
- **comment**: インラインコメント

## 出力フォーマット

Markdown形式で以下の構造に従って出力してください：

- **見出し**: `##` または `###` を使用してセクションを分ける
- **箇条書き**: `-` を使用して項目を列挙
- **参照**: 段落番号は `[段落 X]` の形式で記載
- **強調**: 重要な用語は `**太字**` で強調
- **コードブロック**: 提案する修正文は `` `バッククォート` `` で囲む

出力例：
```markdown
## 契約条項のレビュー

### リスク指摘
- **[段落 5]** 損害賠償の上限が不明確 → 「**直接損害に限り、契約金額を上限とする**」と明記すべき
- **[段落 12]** 解除条件が曖昧 → 具体的な期間（例: `30日前の書面通知`）を追加

### 追跡変更の推奨
- **[段落 3, add]** 秘密保持期間の追加 → **受け入れ推奨**（契約終了後の保護強化）
- **[段落 8, delete]** 一方的な条項の削除 → **受け入れ推奨**（公平性の向上）

### コメントへの対応
- **[comment_id: 1]** 「この条項は必要か？」→ リスク軽減のため保持を推奨
```
"""

SYSTEM_INSTRUCTION = """\
あなたは契約レビュー担当者です。以下の DOCX 解析結果を読み、日本語で簡潔なレビューコメントを箇条書きで出力してください。

## 入力データの構造

入力は以下の構造を持つJSONです：

```json
{
  "path": "ファイルパス",
  "paragraphs": [
    {
      "index": 段落番号（0から始まる）,
      "text": "段落の最終的なテキスト（追跡変更を反映済み）",
      "list": {
        "num_id": "リスト番号ID（リスト項目の場合）",
        "ilvl": "インデントレベル（リスト項目の場合）"
      },
      "events": [
        {
          "kind": "イベント種別",
          "text": "変更対象のテキスト",
          "author": "変更者名",
          "date": "変更日時（ISO 8601形式）",
          "comment_id": "コメントID（コメントの場合）",
          "comment_text": "コメント本文（コメントの場合）"
        }
      ]
    }
  ]
}
```

## フィールドの意味

- **paragraphs**: 文書内の全段落のリスト
- **index**: 段落の位置（参照時に使用）
- **text**: 追跡変更を適用した後の最終テキスト（削除は除外、追加は含む）
- **list**: リスト項目の場合、番号とインデントレベルを含む
- **events**: この段落で発生した変更イベント（時系列順にソート済み）

## イベント種別（kind）

- **add**: テキストの追加（挿入）
- **delete**: テキストの削除
- **move_from**: テキストの移動元
- **move_to**: テキストの移動先
- **comment**: インラインコメント

## 出力フォーマット

Markdown形式で以下の構造に従って出力してください：

- **見出し**: `##` または `###` を使用してセクションを分ける
- **箇条書き**: `-` を使用して項目を列挙
- **参照**: 段落番号は `[段落 X]` の形式で記載
- **強調**: 重要な用語は `**太字**` で強調
- **コードブロック**: 提案する修正文は `` `バッククォート` `` で囲む

出力例：
```markdown
## 契約条項のレビュー

### リスク指摘
- **[段落 5]** 損害賠償の上限が不明確 → 「**直接損害に限り、契約金額を上限とする**」と明記すべき
- **[段落 12]** 解除条件が曖昧 → 具体的な期間（例: `30日前の書面通知`）を追加

### 追跡変更の推奨
- **[段落 3, add]** 秘密保持期間の追加 → **受け入れ推奨**（契約終了後の保護強化）
- **[段落 8, delete]** 一方的な条項の削除 → **受け入れ推奨**（公平性の向上）

### コメントへの対応
- **[comment_id: 1]** 「この条項は必要か？」→ リスク軽減のため保持を推奨
```
"""

DEFAULT_USER_INSTRUCTION = """\
以下のレビュー指示に従ってください：

- リスクのある条項・不足している保護・曖昧な表現を指摘し、修正提案を添える
- 追跡履歴（add/delete）は「受け入れ/却下」の推奨と理由を述べる
- インラインコメントや指示に応答する
- 段落 index や comment_id を参照して特定しやすくする
- 短く行動可能な箇条書きでまとめること
"""


def build_llm_payload(analysis: DocumentAnalysis, user_instruction: str) -> Iterable[Dict]:
    """Compose a payload suitable for LLM's generate_content."""
    return [
        {
            "role": "user",
            "parts": [
                {"text": user_instruction},
                {
                    "text": (
                        "\nDOCX analysis as JSON. Preserve ids and indices when referring "
                        "to items.\n"
                    )
                },
                {"text": json.dumps(analysis.to_dict(), ensure_ascii=False)},
            ],
        },
    ]
