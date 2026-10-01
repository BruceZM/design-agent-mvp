import zipfile
from io import BytesIO
from pathlib import Path

from docx import Document
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

Image.MAX_IMAGE_PIXELS = 20_000_000
IMAGE_LIMIT = 5 * 1024 * 1024
PRD_LIMIT = 20 * 1024 * 1024


def validate_image(content: bytes, filename: str):
    if not content or len(content) > IMAGE_LIMIT:
        raise ValueError("设计稿不能为空，且不能超过 5 MB")
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise ValueError("设计稿仅支持 PNG、JPEG、WebP")
    try:
        with Image.open(BytesIO(content)) as im:
            if im.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("设计稿文件内容不是支持的图片格式")
            if im.width * im.height > 20_000_000:
                raise ValueError("设计稿像素过大，请压缩后上传")
            im.verify()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("无法读取设计稿，请上传有效图片") from exc


def parse_prd(content: bytes, filename: str) -> str:
    if not content or len(content) > PRD_LIMIT:
        raise ValueError("PRD 不能为空，且不能超过 20 MB")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {".md", ".txt"}:
            text = content.decode("utf-8-sig")
        elif suffix == ".docx":
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if (
                    sum(item.file_size for item in archive.infolist())
                    > 40 * 1024 * 1024
                ):
                    raise ValueError("DOCX 解压内容过大")
            doc = Document(BytesIO(content))
            text = "\n".join(
                [p.text for p in doc.paragraphs]
                + [
                    " | ".join(c.text for c in row.cells)
                    for table in doc.tables
                    for row in table.rows
                ]
            )
        elif suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("暂不支持加密 PDF")
            if len(reader.pages) > 80:
                raise ValueError("PDF 最多支持 80 页")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            raise ValueError("PRD 仅支持 UTF-8 Markdown、TXT、DOCX、文字型 PDF")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(
            "PRD 解析失败，请检查文件格式；扫描 PDF 请转换为文字文档"
        ) from exc
    text = text.strip()
    if not text:
        raise ValueError("PRD 没有可读取文字；扫描 PDF 请转换为文字文档")
    if len(text) > 50_000:
        raise ValueError("PRD 超过 MVP 的 50,000 字符限制，请精简需求")
    return text
