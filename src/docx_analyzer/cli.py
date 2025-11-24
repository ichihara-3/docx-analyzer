from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .llm_review import LLMReviewer
from .parser import DocxAnalyzer, load_analysis


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse a DOCX file (content, tracked changes, comments) into JSON and optionally run an LLM review."
    )
    parser.add_argument("docx_path", help="Path to the DOCX file to analyze.")
    parser.add_argument(
        "--review",
        action="store_true",
        help="Run an LLM review (Gemini) using the parsed JSON.",
    )
    parser.add_argument(
        "--prompt",
        type=Path,
        help="Path to a text file containing a custom reviewer prompt.",
    )
    parser.add_argument(
        "--model",
        default="gemini-1.5-flash-002",
        help="Gemini model name to use when --review is set.",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Indentation for JSON output.",
    )
    return parser.parse_args()


def main(args: Optional[argparse.Namespace] = None) -> None:
    args = args or parse_args()
    load_dotenv()
    analysis = load_analysis(args.docx_path)
    print(json.dumps(analysis.to_dict(), ensure_ascii=False, indent=args.indent))
    if args.review:
        prompt_text = args.prompt.read_text(encoding="utf-8") if args.prompt else None
        reviewer = LLMReviewer(model=args.model)
        review_text = reviewer.review(analysis, prompt=prompt_text)
        print("\n--- LLM Review ---")
        print(review_text)


if __name__ == "__main__":
    main()
