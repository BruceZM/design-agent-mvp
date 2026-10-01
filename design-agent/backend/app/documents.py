# 上传材料的确定性校验和文字提取；本模块不调用大模型。
# submit() 先校验，后台 materials() 再提取，避免无效文件进入付费执行阶段。
import zipfile
from io import BytesIO
from pathlib import Path

from docx import Document
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader

Image.MAX_IMAGE_PIXELS = 20_000_000
# 字节大小和解码像素大小分别限制：小压缩文件也可能解码成巨大图片。
IMAGE_LIMIT = 5 * 1024 * 1024
PRD_LIMIT = 20 * 1024 * 1024


def validate_image(content: bytes, filename: str):
    # 同时检查扩展名、图片真实格式和完整性；前端 accept 不能代替后端校验。
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
    # 统一输出纯文字，使下游提示词无需理解四种文档格式。
    # BytesIO 把内存中的上传字节包装成文件对象，不需要额外临时文件。
    if not content or len(content) > PRD_LIMIT:
        raise ValueError("PRD 不能为空，且不能超过 20 MB")
    suffix = Path(filename).suffix.lower()
    try:
        if suffix in {".md", ".txt"}:
            # utf-8-sig 兼容带 BOM 的 UTF-8 文档；不是自动猜测任意编码。
            text = content.decode("utf-8-sig")
        elif suffix == ".docx":
            # DOCX 本质是 ZIP：先限制解压总量，再读取段落和表格。
            # 这里只提取文字，不保留 Word 排版，也不识别嵌入图片。
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
            # pypdf 提取已有文字层；扫描 PDF 无文字时应明确失败。
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("暂不支持加密 PDF")
            if len(reader.pages) > 80:
                raise ValueError("PDF 最多支持 80 页")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            raise ValueError("PRD 仅支持 UTF-8 Markdown、TXT、DOCX、文字型 PDF")
    except ValueError:
        # 自己产生的校验说明原样返回；库抛出的其他异常统一转成可读错误。
        raise
    except Exception as exc:
        raise ValueError(
            "PRD 解析失败，请检查文件格式；扫描 PDF 请转换为文字文档"
        ) from exc
    text = text.strip()
    # 限制提示词输入长度；这里按 Python 字符数计数，并非模型 token 数。
    if not text:
        raise ValueError("PRD 没有可读取文字；扫描 PDF 请转换为文字文档")
    if len(text) > 50_000:
        raise ValueError("PRD 超过 MVP 的 50,000 字符限制，请精简需求")
    return text
