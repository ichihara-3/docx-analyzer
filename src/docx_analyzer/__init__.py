"""
Utilities to parse DOCX files into a structured representation that can be
handed to an LLM, and optionally trigger an automated review pass.
"""

from .parser import DocxAnalyzer, DocumentAnalysis
from .llm_review import LLMReviewer

__all__ = ["DocxAnalyzer", "DocumentAnalysis", "LLMReviewer"]
