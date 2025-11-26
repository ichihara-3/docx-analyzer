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
- **参照**: `[段落 X] "引用テキスト" コメント内容` の形式で記載
  - `[段落 X]` は必須
  - `"引用テキスト"` は任意（特定の箇所を指摘する場合に推奨）
- **強調**: 重要な用語は `**太字**` で強調
- **コードブロック**: 提案する修正文は `` `バッククォート` `` で囲む

出力例：
```markdown
## 契約条項のレビュー

### リスク指摘
- **[段落 5] "損害賠償の上限"** 上限が不明確 → 「**直接損害に限り、契約金額を上限とする**」と明記すべき
- **[段落 12]** 解除条件が曖昧 → 具体的な期間（例: `30日前の書面通知`）を追加

### 追跡変更の推奨
- **[段落 3, add] "秘密保持期間"** 追加 → **受け入れ推奨**（契約終了後の保護強化）
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

## 出力フォーマット（重要）

Markdown形式で以下の構造に従って出力してください：

- **見出し**: `##` または `###` を使用してセクションを分ける
- **箇条書き**: `-` を使用して項目を列挙
- **段落参照（必須）**: **各レビュー項目の冒頭に必ず `[段落 X]` の形式で段落番号を記載してください**
  - X は入力JSONの `index` フィールドの値を使用
  - 特定の箇所を指摘する場合は、続けて `"引用テキスト"` を記載してください
  - 例: `[段落 5] "損害賠償" 金額が低すぎます`
  - この形式は自動処理のために必須です
  - 段落番号のない指摘は処理できません
- **強調**: 重要な用語は `**太字**` で強調
- **コードブロック**: 提案する修正文は `` `バッククォート` `` で囲む

出力例：
```markdown
## 契約条項のレビュー

### リスク指摘
- [段落 5] "損害賠償の上限" 不明確です → 「**直接損害に限り、契約金額を上限とする**」と明記すべき
- [段落 12] 解除条件が曖昧 → 具体的な期間（例: `30日前の書面通知`）を追加

### 追跡変更の推奨
- [段落 3] "秘密保持期間" 追加 → **受け入れ推奨**（契約終了後の保護強化）
- [段落 8] 一方的な条項の削除 → **受け入れ推奨**（公平性の向上）

### コメントへの対応
- [段落 15] コメント「この条項は必要か？」→ リスク軽減のため保持を推奨
```

**重要**: 上記の例のように、すべての箇条書き項目は `[段落 X]` で始めてください。
"""

DEFAULT_USER_INSTRUCTION = """\
以下のレビュー指示に従ってください：

- リスクのある条項・不足している保護・曖昧な表現を指摘し、修正提案を添える
- 追跡履歴（add/delete）は「受け入れ/却下」の推奨と理由を述べる
- インラインコメントや指示に応答する
- **必ず各指摘の冒頭に `[段落 X]` の形式で段落番号を記載してください**（X は入力JSONの index）
- 特定の語句への指摘は `[段落 X] "対象語句" コメント` のように引用符で囲んで指定する
- 段落番号のない指摘は自動処理できません
- 短く行動可能な箇条書きでまとめること
"""

# Prompt templates for different review types
PROMPT_TEMPLATES = {
    "default": DEFAULT_USER_INSTRUCTION,
    "risk_focus": """\
以下のレビュー指示に従ってください：

- **リスク重点レビュー**: 契約上のリスクを最優先で評価
- 損害賠償、解除条件、秘密保持、知的財産権などの重要条項を重点的に分析
- リスクレベル（高/中/低）を明示
- 各リスクに対する具体的な軽減策を提案
- **必ず各指摘の冒頭に `[段落 X]` の形式で段落番号を記載してください**（X は入力JSONの index）
- 特定の語句への指摘は `[段落 X] "対象語句" コメント` のように引用符で囲んで指定する
- 段落番号のない指摘は自動処理できません
- 優先度順に箇条書きでまとめること
""",
    "change_summary": """\
以下のレビュー指示に従ってください：

- **変更履歴サマリー**: 追跡変更の内容を要約
- 追加（add）、削除（delete）、移動（move）の各変更を分類
- 各変更の影響度を評価（重要/通常/軽微）
- 変更の受け入れ/却下の推奨と理由を明確に述べる
- 変更者（author）と日時（date）を含めて記載
- **必ず各指摘の冒頭に `[段落 X]` の形式で段落番号を記載してください**（X は入力JSONの index）
- 特定の語句への指摘は `[段落 X] "対象語句" コメント` のように引用符で囲んで指定する
- 段落番号のない指摘は自動処理できません
""",
    "comment_review": """\
以下のレビュー指示に従ってください：

- **コメント対応チェック**: インラインコメントへの対応を重点的に確認
- 各コメント（comment_id）に対する具体的な回答や対応案を提示
- コメントで指摘された問題点の妥当性を評価
- 対応の優先度を明示（必須/推奨/任意）
- **必ず各指摘の冒頭に `[段落 X]` の形式で段落番号を記載してください**（X は入力JSONの index）
- 特定の語句への指摘は `[段落 X] "対象語句" コメント` のように引用符で囲んで指定する
- 段落番号のない指摘は自動処理できません
- 対応が必要なコメントを優先順に箇条書きでまとめること
""",
}


def get_prompt_template(template_name: str) -> str:
    """Get a prompt template by name.
    
    Args:
        template_name: Name of the template (default, risk_focus, change_summary, comment_review)
        
    Returns:
        The prompt template string, or DEFAULT_USER_INSTRUCTION if not found
    """
    return PROMPT_TEMPLATES.get(template_name, DEFAULT_USER_INSTRUCTION)


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


class CommentLocator:
    """Identifies precise start/end text for comments within a paragraph."""

    def __init__(self, model: str = "gemini-2.5-flash"):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=api_key)
        self.model_name = model

    def locate_comments(
        self, paragraph_text: str, comments: list[str]
    ) -> list[dict[str, str]]:
        """Identify start and end text for each comment in the paragraph.

        Args:
            paragraph_text: The text of the paragraph.
            comments: List of comment texts to locate.

        Returns:
            List of dictionaries with 'start' and 'end' keys for each comment.
            If location cannot be determined, 'start' and 'end' will be empty strings.
        """
        if not comments:
            return []

        prompt = """\
You are a helper that identifies the text range for comments.
Given a paragraph text and a list of comments, determine the most appropriate "start text" and "end text" within the paragraph for each comment to attach to.

# Rules
- The "start text" and "end text" MUST be exact substrings of the paragraph.
- If the comment refers to a specific phrase, use that phrase as start/end.
- If the comment refers to a general concept, pick the most relevant sentence or clause.
- If you cannot determine a specific range, return empty strings for start/end.
- Return ONLY valid JSON.

# Input
Paragraph: {paragraph}

Comments:
{comments_list}

# Output Format (JSON)
[
  {{
    "comment_index": 0,
    "start": "start text substring",
    "end": "end text substring"
  }}
]
"""
        comments_formatted = "\n".join(
            [f"{i}: {c}" for i, c in enumerate(comments)]
        )
        content = prompt.format(
            paragraph=paragraph_text, comments_list=comments_formatted
        )

        model = genai.GenerativeModel(self.model_name)
        try:
            response = model.generate_content(
                content,
                generation_config=genai.types.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            result = json.loads(response.text)
            
            # Validate and sort by index
            locations = [{"start": "", "end": ""} for _ in comments]
            for item in result:
                idx = item.get("comment_index")
                if isinstance(idx, int) and 0 <= idx < len(comments):
                    locations[idx] = {
                        "start": item.get("start", ""),
                        "end": item.get("end", ""),
                    }
            return locations
        except Exception:
            # Fallback to empty locations on error
            return [{"start": "", "end": ""} for _ in comments]
