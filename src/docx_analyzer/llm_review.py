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
        model: str = "gemini-1.5-flash-002",
        system_prompt: Optional[str] = None,
    ):
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY is not set")
        genai.configure(api_key=api_key)
        self.model_name = model
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    def review(self, analysis: DocumentAnalysis, prompt: Optional[str] = None) -> str:
        """Send the analysis and a reviewer prompt to the LLM, return plain text."""
        system_text = prompt or self.system_prompt
        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=system_text,
        )
        content = build_llm_payload(analysis)
        response = model.generate_content(content)
        return response.text or ""


DEFAULT_SYSTEM_PROMPT = """\
あなたは契約レビュー担当者です。以下の DOCX 解析結果（段落・リスト・追跡履歴・コメント）を読み、日本語で簡潔なレビューコメントを箇条書きで出力してください。
- リスクのある条項・不足している保護・曖昧な表現を指摘し、修正提案を添える
- 追跡履歴は「受け入れ/却下」の推奨と理由を述べる
- インラインコメントや指示に応答する
- 段落 index や comment_id を参照して特定しやすくする
短く行動可能な箇条書きでまとめること。
"""


def build_llm_payload(analysis: DocumentAnalysis) -> Iterable[Dict]:
    """Compose a payload suitable for Gemini's generate_content."""
    return [
        {
            "role": "user",
            "parts": [
                {
                    "text": (
                        "DOCX analysis as JSON. Preserve ids and indices when referring "
                        "to items.\n"
                    )
                },
                {"text": json.dumps(analysis.to_dict(), ensure_ascii=False)},
            ],
        },
    ]
