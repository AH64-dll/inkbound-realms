"""Ordered, bounded document ingestion with full-text chunk coverage."""
from __future__ import annotations

import hashlib
import posixpath
import re
import zipfile
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class Book:
    title: str
    digest: str
    text: str
    chunks: tuple[Chunk, ...]


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"): self.hidden += 1
        if tag in ("p", "br", "div", "h1", "h2", "h3"): self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"): self.hidden = max(0, self.hidden - 1)
        if tag in ("p", "div", "h1", "h2", "h3"): self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def read_text(path: Path):
    raw = path.read_bytes()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    if b"\x00" in raw[:1000]:
        try: return raw.decode("utf-16-le")
        except UnicodeDecodeError: return raw.decode("utf-16-be")
    try: return raw.decode("utf-8")
    except UnicodeDecodeError: return raw.decode("cp1252")


def read_epub(path: Path):
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 100 * 1024 * 1024:
            raise ValueError("EPUB expanded content exceeds 100 MiB")
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        rootfile = next((e.get("full-path") for e in container.iter() if e.tag.endswith("rootfile")), None)
        if not rootfile:
            raise ValueError("EPUB has no package root")
        opf = ET.fromstring(archive.read(rootfile))
        manifest = {e.get("id"): e.get("href") for e in opf.iter() if e.tag.endswith("}item")}
        ordered = [e.get("idref") for e in opf.iter() if e.tag.endswith("}itemref") and e.get("linear", "yes") != "no"]
        if not ordered:
            raise ValueError("EPUB has no reading spine")
        parts = []
        for eid in ordered:
            if eid not in manifest:
                raise ValueError("EPUB spine references a missing manifest entry")
            name = posixpath.normpath(posixpath.join(posixpath.dirname(rootfile), unquote(manifest[eid].split("#")[0])))
            if name.startswith("../") or name.startswith("/"):
                raise ValueError("Invalid EPUB content path")
            parser = TextHTML(); parser.feed(archive.read(name).decode("utf-8-sig"))
            parts.append("".join(parser.parts))
        return "\n\n".join(parts)


def ingest(path: str | Path, *, chunk_chars: int = 9000) -> Book:
    path = Path(path)
    if not 500 <= chunk_chars <= 24000:
        raise ValueError("Chunk size must be 500..24000 characters")
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Book exceeds 100 MiB")
    if path.suffix.lower() == ".txt":
        text = read_text(path)
    elif path.suffix.lower() == ".epub":
        text = read_epub(path)
    elif path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(path)
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs require a decrypted reading copy")
        # Fail explicitly on extraction errors rather than silently omitting pages.
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        raise ValueError("Use a TXT, PDF or EPUB book")
    text = text.replace("\x00", "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        raise ValueError("Book has no extractable text; scanned PDFs need OCR first")
    digest = hashlib.sha256(text.encode()).hexdigest()
    chunks = []; start = 0
    while start < len(text):
        end = min(len(text), start + chunk_chars)
        if end < len(text):
            boundary = text.rfind("\n", start + chunk_chars // 2, end)
            if boundary >= 0: end = boundary + 1
        chunks.append(Chunk(f"chunk.{len(chunks):04d}", text[start:end], start, end)); start = end
    return Book(path.stem, digest, text, tuple(chunks))
