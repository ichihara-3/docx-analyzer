from __future__ import annotations

import json
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from lxml import etree


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


def _strip_ns(tag: str) -> str:
    """Strip the XML namespace from a tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _text_in_element(el: etree._Element) -> str:
    """Return concatenated text for all w:t descendants."""
    parts: List[str] = []
    for t in el.xpath(".//w:t", namespaces=NS):
        if t.text:
            parts.append(t.text)
    return "".join(parts)


@dataclass
class ChangeEvent:
    kind: str  # add | delete | move_from | move_to | comment
    text: str
    author: Optional[str] = None
    date: Optional[str] = None
    comment_id: Optional[str] = None
    comment_text: Optional[str] = None


@dataclass
class ListInfo:
    num_id: Optional[str] = None
    ilvl: Optional[str] = None

    def is_list_item(self) -> bool:
        return self.num_id is not None and self.ilvl is not None


@dataclass
class ParagraphAnalysis:
    index: int
    text: str
    list_info: ListInfo = field(default_factory=ListInfo)
    events: List[ChangeEvent] = field(default_factory=list)


@dataclass
class DocumentAnalysis:
    path: str
    paragraphs: List[ParagraphAnalysis]

    def to_dict(self) -> Dict:
        return {
            "path": self.path,
            "paragraphs": [
                {
                    "index": p.index,
                    "text": p.text,
                    "list": asdict(p.list_info),
                    "events": [asdict(ev) for ev in p.events],
                }
                for p in self.paragraphs
            ],
        }

    def to_json(self, **json_kwargs: Dict) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, **json_kwargs)


class DocxAnalyzer:
    """Parse DOCX content (including tracked changes and comments) into JSON."""

    def __init__(self, path: str):
        self.path = str(path)
        self._zip = zipfile.ZipFile(self.path)
        self.comments: Dict[str, Dict[str, Optional[str]]] = self._load_comments()

    def analyze(self) -> DocumentAnalysis:
        document_xml = self._zip.read("word/document.xml")
        root = etree.fromstring(document_xml)
        paragraphs: List[ParagraphAnalysis] = []
        for idx, p in enumerate(root.xpath(".//w:body/w:p", namespaces=NS)):
            paragraphs.append(self._analyze_paragraph(idx, p))
        return DocumentAnalysis(path=self.path, paragraphs=paragraphs)

    # --- internal parsing helpers -------------------------------------------------

    def _load_comments(self) -> Dict[str, Dict[str, Optional[str]]]:
        """Return mapping of comment id -> {text, date}."""
        try:
            data = self._zip.read("word/comments.xml")
        except KeyError:
            return {}
        root = etree.fromstring(data)
        comments: Dict[str, Dict[str, Optional[str]]] = {}
        for comment in root.xpath(".//w:comment", namespaces=NS):
            cid = comment.get(f"{{{NS['w']}}}id")
            date = comment.get(f"{{{NS['w']}}}date")
            comments[cid] = {
                "text": _text_in_element(comment),
                "date": date,
            }
        return comments

    def _list_info(self, para: etree._Element) -> ListInfo:
        """Extract numbering details for list detection."""
        num_id_nodes = para.xpath("./w:pPr/w:numPr/w:numId", namespaces=NS)
        ilvl_nodes = para.xpath("./w:pPr/w:numPr/w:ilvl", namespaces=NS)
        num_id = num_id_nodes[0].get(f"{{{NS['w']}}}val") if num_id_nodes else None
        ilvl = ilvl_nodes[0].get(f"{{{NS['w']}}}val") if ilvl_nodes else None
        return ListInfo(num_id=num_id, ilvl=ilvl)

    def _analyze_paragraph(self, idx: int, para: etree._Element) -> ParagraphAnalysis:
        current_text: List[str] = []
        events: List[ChangeEvent] = []
        active_comment_buffers: Dict[str, List[str]] = {}

        def flush_comment(id_: str):
            text = "".join(active_comment_buffers.get(id_, []))
            comment_data = self.comments.get(id_, {})
            event = ChangeEvent(
                kind="comment",
                text=text,
                comment_id=id_,
                comment_text=comment_data.get("text"),
                date=comment_data.get("date"),
            )
            events.append(event)
            active_comment_buffers.pop(id_, None)

        def walk(node: etree._Element, deletion: bool = False):
            for child in node:
                tag = _strip_ns(child.tag)
                if tag == "ins":
                    text = _text_in_element(child)
                    events.append(
                        ChangeEvent(
                            kind="add",
                            text=text,
                            author=child.get(f"{{{NS['w']}}}author"),
                            date=child.get(f"{{{NS['w']}}}date"),
                        )
                    )
                    walk(child, deletion=False)
                    if text:
                        current_text.append(text)
                        for buf in active_comment_buffers.values():
                            buf.append(text)
                elif tag == "del":
                    text = _text_in_element(child)
                    events.append(
                        ChangeEvent(
                            kind="delete",
                            text=text,
                            author=child.get(f"{{{NS['w']}}}author"),
                            date=child.get(f"{{{NS['w']}}}date"),
                        )
                    )
                    walk(child, deletion=True)
                    # deleted text is intentionally excluded from current_text
                    if text:
                        for buf in active_comment_buffers.values():
                            buf.append(text)
                elif tag == "moveFrom":
                    text = _text_in_element(child)
                    events.append(
                        ChangeEvent(
                            kind="move_from",
                            text=text,
                            author=child.get(f"{{{NS['w']}}}author"),
                            date=child.get(f"{{{NS['w']}}}date"),
                        )
                    )
                    walk(child, deletion=True)
                elif tag == "moveTo":
                    text = _text_in_element(child)
                    events.append(
                        ChangeEvent(
                            kind="move_to",
                            text=text,
                            author=child.get(f"{{{NS['w']}}}author"),
                            date=child.get(f"{{{NS['w']}}}date"),
                        )
                    )
                    walk(child, deletion=False)
                    if text:
                        current_text.append(text)
                        for buf in active_comment_buffers.values():
                            buf.append(text)
                elif tag == "commentRangeStart":
                    cid = child.get(f"{{{NS['w']}}}id")
                    if cid is not None:
                        active_comment_buffers[cid] = []
                elif tag == "commentRangeEnd":
                    cid = child.get(f"{{{NS['w']}}}id")
                    if cid is not None and cid in active_comment_buffers:
                        flush_comment(cid)
                elif tag in {"r", "hyperlink"}:
                    text = _text_in_element(child)
                    if text:
                        if not deletion:
                            current_text.append(text)
                        for buf in active_comment_buffers.values():
                            buf.append(text)
                    # recurse to catch nested comment markers inside runs
                    walk(child, deletion=deletion)
                else:
                    walk(child, deletion=deletion)

        walk(para, deletion=False)
        # flush any unclosed comment ranges
        for cid in list(active_comment_buffers.keys()):
            flush_comment(cid)
        
        # Sort events by date. Events without date come first (or last? let's stick to stable sort)
        # Using empty string for None ensures they are grouped together.
        events.sort(key=lambda x: x.date or "")

        text_value = "".join(current_text).strip()
        return ParagraphAnalysis(
            index=idx,
            text=text_value,
            list_info=self._list_info(para),
            events=events,
        )


def load_analysis(path: str) -> DocumentAnalysis:
    analyzer = DocxAnalyzer(path)
    return analyzer.analyze()
