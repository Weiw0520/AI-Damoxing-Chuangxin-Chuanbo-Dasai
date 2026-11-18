import io
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from backend.a_compat.store import failure

MAX_BYTES = 5 * 1024 * 1024
MAX_CHARS = 20000


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.ignored = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored += 1
        if not self.ignored and tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignored:
            self.ignored -= 1
        if not self.ignored and tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.ignored:
            self.parts.append(data)


def decode(data):
    encodings = ["utf-16"] if data.startswith((b"\xff\xfe", b"\xfe\xff")) else ["utf-8-sig", "gb18030"]
    for encoding in encodings:
        try:
            text = data.decode(encoding)
            if "\x00" in text:
                raise ValueError("binary")
            return text
        except (UnicodeError, ValueError):
            pass
    raise failure(422, "INVALID_ENCODING", "文件不是可读取的 UTF-8、UTF-16 或 GB18030 纯文本。")


def extract(filename, data):
    if len(data) > MAX_BYTES:
        raise failure(413, "FILE_TOO_LARGE", "单个文件不能超过 5 MB。")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".html", ".htm", ".docx"}:
        raise failure(415, "UNSUPPORTED_FILE_TYPE", "支持文本、HTML 和 DOCX；暂不支持 PDF、图片或旧版 DOC。")
    if not data:
        raise failure(422, "EMPTY_FILE", "文件为空。")
    kind = "text"
    if suffix == ".docx":
        kind = "docx"
        try:
            with ZipFile(io.BytesIO(data)) as archive:
                infos = archive.infolist()
                if len(infos) > 2048 or sum(i.file_size for i in infos) > 20 * 1024 * 1024:
                    raise failure(413, "DOCX_TOO_LARGE", "DOCX 解压后内容过大。")
                info = archive.getinfo("word/document.xml")
                if info.file_size > MAX_BYTES or info.flag_bits & 1:
                    raise failure(413, "DOCX_TOO_LARGE", "DOCX 正文过大或已加密。")
                xml = archive.read(info)
            if re.search(br"<!\s*(DOCTYPE|ENTITY)", xml, re.I):
                raise failure(422, "INVALID_DOCX", "DOCX 包含不支持的 XML 声明。")
            root = ElementTree.fromstring(xml)
            paragraphs = []
            for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
                paragraphs.append("".join(n.text or "" for n in paragraph.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")))
            text = "\n".join(paragraphs)
        except (BadZipFile, KeyError, ElementTree.ParseError, RuntimeError) as error:
            raise failure(422, "INVALID_DOCX", "DOCX 损坏、已加密或缺少可读取正文。") from error
    else:
        text = decode(data)
        if suffix in {".html", ".htm"}:
            kind = "html"
            parser = TextHTML()
            parser.feed(text)
            text = "".join(parser.parts)
    text = text.strip()
    if not text:
        raise failure(422, "EMPTY_FILE", "文件没有可用正文。")
    return {"filename": filename, "kind": kind, "text": text[:MAX_CHARS], "chars": min(len(text), MAX_CHARS),
            "truncated": len(text) > MAX_CHARS, "limit": MAX_CHARS}
