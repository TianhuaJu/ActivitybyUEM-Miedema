# -*- coding: utf-8 -*-
"""
Document Learner - 文档知识导入器
==================================
从 PDF / TXT 教材中提取文本，按章节/段落智能分段，
存入知识库供 AI 助手在对话中检索引用。

支持格式:
- PDF（通过 PyMuPDF / fitz）
- 纯文本 TXT
- Markdown (.md)
"""

import os
import re
import time
from typing import List, Dict, Any, Tuple, Optional, Callable


# ==================== 文本提取 ====================

def extract_text_from_pdf(filepath: str, vision=None) -> Tuple[str, Dict[str, Any]]:
    """
    从PDF文件提取全文，包括表格内容和图片信息

    参数:
        filepath: PDF文件路径
        vision: VisionRecognizer实例（可选，用于AI视觉识别图片和表格）

    返回:
        (全文文本, 元信息字典)
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise ImportError(
            "需要安装 PyMuPDF 库来读取 PDF 文件。\n"
            "请运行: pip install PyMuPDF"
        )

    doc = fitz.open(filepath)
    meta = {
        "title": doc.metadata.get("title", "") or os.path.basename(filepath),
        "author": doc.metadata.get("author", ""),
        "pages": doc.page_count,
        "filename": os.path.basename(filepath),
    }

    page_contents = []
    table_count = 0
    image_count = 0
    ocr_state = {"tested": False, "available": False}

    for page_num, page in enumerate(doc, start=1):
        # 普通文本
        text = page.get_text("text")
        if text.strip():
            page_contents.append(text)

        # 表格提取（优先AI视觉，回退到文本提取）
        tables = _extract_tables_from_page(page, page_num, vision)
        if tables:
            table_count += len(tables)
            page_contents.extend(tables)

        # 图片上下文提取（优先AI视觉，回退到OCR）
        img_texts = _extract_image_context(page, doc, page_num, ocr_state, vision)
        if img_texts:
            image_count += len(img_texts)
            page_contents.extend(img_texts)

    doc.close()

    meta["tables_extracted"] = table_count
    meta["images_processed"] = image_count
    meta["ocr_available"] = ocr_state.get("available", False)
    meta["ai_vision"] = vision is not None and vision.is_available()

    return "\n\n".join(page_contents), meta


def extract_text_from_txt(filepath: str) -> Tuple[str, Dict[str, Any]]:
    """从纯文本文件提取内容"""
    # 尝试多种编码
    for enc in ("utf-8", "gbk", "gb2312", "gb18030", "latin-1"):
        try:
            with open(filepath, "r", encoding=enc) as f:
                text = f.read()
            meta = {
                "title": os.path.basename(filepath),
                "author": "",
                "pages": 0,
                "filename": os.path.basename(filepath),
            }
            return text, meta
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"无法识别文件编码: {filepath}")


def extract_text(filepath: str, vision=None) -> Tuple[str, Dict[str, Any]]:
    """根据文件扩展名选择提取方法"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath, vision=vision)
    elif ext in (".txt", ".md", ".rst", ".text"):
        return extract_text_from_txt(filepath)
    else:
        raise ValueError(f"不支持的文件格式: {ext}（支持 .pdf, .txt, .md）")


# ==================== 智能分段 ====================

# 章节标题模式（中文教材常见格式）
_HEADING_PATTERNS = [
    # 第X章 / 第X节
    re.compile(r'^第[一二三四五六七八九十\d]+[章节]\s*.+', re.MULTILINE),
    # X.X / X.X.X 编号标题
    re.compile(r'^\d+\.\d+(?:\.\d+)?\s+\S+', re.MULTILINE),
    # 全大写英文标题 (CHAPTER / SECTION)
    re.compile(r'^[A-Z][A-Z\s]{5,}$', re.MULTILINE),
    # 【标题】格式
    re.compile(r'^【.+】\s*$', re.MULTILINE),
]

# 材料/冶金/热力学领域关键词（用于过滤无关内容和标记标签）
_DOMAIN_KEYWORDS = {
    "活度", "活度系数", "相互作用系数", "热力学", "Gibbs", "自由能",
    "焓", "熵", "化学势", "相图", "液相线", "固相线", "共晶",
    "合金", "钢", "铁", "铜", "铝", "镍", "锌", "锰", "铬",
    "Fe", "Cu", "Al", "Ni", "Zn", "Mn", "Cr", "Si", "Ti", "Nb", "V",
    "溶质", "溶剂", "溶液", "熔体", "渣",
    "Wagner", "Miedema", "Darken", "Elliott", "Muggianu",
    "摩尔分数", "质量分数", "析出", "凝固", "相变",
    "一阶", "二阶", "无限稀释", "ε", "γ", "μ",
    "温度", "平衡", "动力学", "扩散",
    "冶金", "炼钢", "精炼", "脱氧", "脱硫",
    "activity", "coefficient", "interaction", "thermodynamic",
    "enthalpy", "entropy", "Gibbs", "phase", "alloy",
    "liquidus", "solidus", "eutectic", "precipitation",
}

# 元素符号集（用于自动提取标签）
_ELEMENT_SYMBOLS = {
    "H", "He", "Li", "Be", "B", "C", "N", "O", "F", "Ne",
    "Na", "Mg", "Al", "Si", "P", "S", "Cl", "Ar",
    "K", "Ca", "Sc", "Ti", "V", "Cr", "Mn", "Fe", "Co", "Ni",
    "Cu", "Zn", "Ga", "Ge", "As", "Se", "Br", "Kr",
    "Rb", "Sr", "Y", "Zr", "Nb", "Mo", "Ru", "Rh", "Pd", "Ag",
    "Cd", "In", "Sn", "Sb", "Te", "I", "Xe",
    "Cs", "Ba", "La", "Hf", "Ta", "W", "Re", "Os", "Ir", "Pt",
    "Au", "Hg", "Tl", "Pb", "Bi",
}


# ==================== 表格与图片提取 ====================

def _extract_tables_from_page(page, page_num: int, vision=None) -> List[str]:
    """从PDF页面提取表格（优先AI视觉识别，回退到文本提取）"""
    tables_text = []
    try:
        tabs = page.find_tables()
        for table in tabs.tables:
            data = table.extract()
            if not data or len(data) < 2:
                continue

            # 优先使用AI视觉识别表格
            if vision and vision.is_available():
                try:
                    import fitz
                    clip = fitz.Rect(table.bbox)
                    clip.x0 = max(0, clip.x0 - 5)
                    clip.y0 = max(0, clip.y0 - 5)
                    clip.x1 += 5
                    clip.y1 += 5
                    pix = page.get_pixmap(clip=clip, dpi=200)
                    img_bytes = pix.tobytes("png")
                    ai_text = vision.recognize_table(img_bytes, "image/png")
                    if ai_text and "无有效内容" not in ai_text:
                        header = (f"[表格(AI识别) - 第{page_num}页, "
                                  f"{table.row_count}行x{table.col_count}列]")
                        tables_text.append(f"{header}\n{ai_text}")
                        continue
                except Exception:
                    pass

            # 回退到PyMuPDF文本提取
            try:
                md = table.to_markdown()
            except AttributeError:
                md = _table_data_to_markdown(data)
            if md and md.strip():
                header = f"[表格 - 第{page_num}页, {table.row_count}行x{table.col_count}列]"
                tables_text.append(f"{header}\n{md}")
    except Exception:
        pass
    return tables_text


def _table_data_to_markdown(data: List[List]) -> str:
    """将表格数据（二维列表）转换为Markdown表格字符串"""
    if not data:
        return ""
    header = data[0]
    cols = len(header)
    lines = []
    cells = [str(c or "").replace("|", "\\|").replace("\n", " ") for c in header]
    lines.append("| " + " | ".join(cells) + " |")
    lines.append("| " + " | ".join(["---"] * cols) + " |")
    for row in data[1:]:
        cells = [str(c or "").replace("|", "\\|").replace("\n", " ") for c in row]
        while len(cells) < cols:
            cells.append("")
        lines.append("| " + " | ".join(cells[:cols]) + " |")
    return "\n".join(lines)


def _get_text_blocks_with_position(page) -> List[Dict]:
    """获取页面上所有文本块及其位置坐标"""
    blocks = []
    try:
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:
                text = ""
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text += span.get("text", "")
                text = text.strip()
                if text:
                    blocks.append({"text": text, "bbox": block["bbox"]})
    except Exception:
        pass
    return blocks


def _get_image_rect(page, xref: int):
    """获取图片在页面上的位置矩形"""
    try:
        rects = page.get_image_rects(xref)
        if rects:
            return rects[0]
    except (AttributeError, Exception):
        pass
    try:
        return page.get_image_bbox(xref)
    except Exception:
        return None


def _find_nearby_caption(img_rect, text_blocks: list, margin: float = 60.0) -> str:
    """查找图片附近的说明文字（图注）"""
    captions = []
    ix0, iy0, ix1, iy1 = img_rect.x0, img_rect.y0, img_rect.x1, img_rect.y1

    for block in text_blocks:
        bx0, by0, bx1, by1 = block["bbox"]
        # 水平方向需有重叠
        if bx1 < ix0 - margin or bx0 > ix1 + margin:
            continue
        text = block["text"]
        # 图片下方（最常见的图注位置）
        if 0 <= by0 - iy1 < margin:
            if re.search(r'(图\s*[\d.]+|Fig\.?\s*[\d.]+|Figure\s*[\d.]+|'
                         r'表\s*[\d.]+|Table\s*[\d.]+)', text, re.IGNORECASE):
                captions.insert(0, text)
            else:
                captions.append(text)
        # 图片上方
        elif 0 <= iy0 - by1 < margin * 0.5:
            if re.search(r'(图\s*[\d.]+|Fig\.?\s*[\d.]+|Figure\s*[\d.]+)',
                         text, re.IGNORECASE):
                captions.insert(0, text)
    return " ".join(captions[:3]).strip() if captions else ""


def _try_ocr_image(doc, xref: int, ocr_state: dict) -> str:
    """
    尝试对图片进行OCR识别（需要系统安装 Tesseract-OCR）

    参数:
        doc: PyMuPDF Document 对象
        xref: 图片的交叉引用号
        ocr_state: 可变字典，记录OCR是否可用以避免重复尝试
    """
    if ocr_state.get("tested") and not ocr_state.get("available"):
        return ""
    try:
        import fitz
        pix = fitz.Pixmap(doc, xref)
        if pix.n - pix.alpha > 3:
            pix = fitz.Pixmap(fitz.csRGB, pix)
        if pix.width < 100 or pix.height < 100:
            return ""
        pdf_bytes = pix.pdfocr_tobytes(language="eng+chi_sim")
        ocr_state["tested"] = True
        ocr_state["available"] = True
        ocr_doc = fitz.open("pdf", pdf_bytes)
        text = ""
        for p in ocr_doc:
            text += p.get_text()
        ocr_doc.close()
        return text.strip()
    except Exception:
        if not ocr_state.get("tested"):
            ocr_state["tested"] = True
            ocr_state["available"] = False
        return ""


def _extract_image_context(page, doc, page_num: int, ocr_state: dict,
                           vision=None) -> List[str]:
    """从PDF页面提取图片上下文信息（优先AI视觉，回退到OCR）"""
    results = []
    try:
        images = page.get_images(full=True)
        if not images:
            return results

        text_blocks = _get_text_blocks_with_position(page)
        processed_xrefs = set()

        for img_info in images:
            xref = img_info[0]
            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)

            width, height = img_info[2], img_info[3]
            if width < 80 or height < 80:
                continue

            img_rect = _get_image_rect(page, xref)

            # 查找图片说明文字
            caption = ""
            if img_rect and text_blocks:
                caption = _find_nearby_caption(img_rect, text_blocks)
            if caption:
                results.append(f"[图片说明 - 第{page_num}页] {caption}")

            # 优先使用AI视觉识别
            recognized = False
            if vision and vision.is_available():
                try:
                    import fitz
                    img_data = doc.extract_image(xref)
                    img_bytes = img_data["image"]
                    ext = img_data.get("ext", "png")
                    mime = f"image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
                    ai_text = vision.recognize_image(img_bytes, mime)
                    if ai_text and "无有效内容" not in ai_text:
                        results.append(
                            f"[图片内容(AI识别) - 第{page_num}页]\n{ai_text}")
                        recognized = True
                except Exception:
                    pass

            # 回退到OCR
            if not recognized:
                ocr_text = _try_ocr_image(doc, xref, ocr_state)
                if ocr_text:
                    if len(ocr_text) > 500:
                        ocr_text = ocr_text[:500] + "..."
                    results.append(f"[图片内容(OCR) - 第{page_num}页]\n{ocr_text}")
    except Exception:
        pass
    return results


def _find_section_breaks(text: str) -> List[int]:
    """查找章节分隔位置"""
    breaks = set()
    for pattern in _HEADING_PATTERNS:
        for m in pattern.finditer(text):
            breaks.add(m.start())
    return sorted(breaks)


def _extract_tags(text: str) -> str:
    """从文本中提取领域关键词标签"""
    tags = set()
    # 匹配元素符号（作为独立单词出现）
    for sym in _ELEMENT_SYMBOLS:
        if re.search(r'\b' + sym + r'\b', text):
            tags.add(sym)
    # 匹配领域关键词
    text_lower = text.lower()
    for kw in _DOMAIN_KEYWORDS:
        if kw.lower() in text_lower:
            tags.add(kw)
    # 限制标签数量
    return ",".join(sorted(tags)[:15])


def _compute_relevance(text: str) -> float:
    """计算文本片段与材料/冶金/热力学领域的相关度 (0-1)"""
    if not text.strip():
        return 0.0
    hits = 0
    for kw in _DOMAIN_KEYWORDS:
        if len(kw) <= 3:
            # 短关键词用词边界匹配，避免 "Ti" 匹配 "beautiful" 等误报
            if re.search(r'\b' + re.escape(kw) + r'\b', text):
                hits += 1
        else:
            if kw.lower() in text.lower():
                hits += 1
    # 基础分 0.5，每个关键词 +0.05，上限 1.0
    return min(1.0, 0.5 + hits * 0.05)


def _generate_topic(text: str, index: int, source_name: str) -> str:
    """为文本片段自动生成主题名"""
    # 取前60个字符作为主题
    first_line = text.strip().split("\n")[0].strip()
    if len(first_line) > 60:
        first_line = first_line[:57] + "..."
    # 清理特殊字符
    first_line = re.sub(r'\s+', ' ', first_line)
    if not first_line:
        first_line = f"段落 {index + 1}"
    return f"[{source_name}] {first_line}"


def chunk_text(text: str, max_chunk_size: int = 800,
               min_chunk_size: int = 100,
               overlap: int = 50) -> List[str]:
    """
    将文本智能分段

    策略:
    1. 优先按章节标题分割
    2. 章节内按段落（双换行）分割
    3. 过长段落按句子边界分割
    4. 段落间保留少量重叠以保持上下文连贯
    """
    if not text.strip():
        return []

    # Step 1: 按章节标题分割
    section_breaks = _find_section_breaks(text)
    if section_breaks:
        sections = []
        for i, start in enumerate(section_breaks):
            end = section_breaks[i + 1] if i + 1 < len(section_breaks) else len(text)
            section = text[start:end].strip()
            if section:
                sections.append(section)
        # 章节之前的内容（序言等）
        if section_breaks[0] > 0:
            preamble = text[:section_breaks[0]].strip()
            if preamble:
                sections.insert(0, preamble)
    else:
        sections = [text]

    # Step 2: 将每个章节按段落拆分
    chunks = []
    for section in sections:
        paragraphs = re.split(r'\n\s*\n', section)
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) + 1 <= max_chunk_size:
                current_chunk = (current_chunk + "\n\n" + para).strip()
            else:
                # 当前块已满，保存
                if len(current_chunk) >= min_chunk_size:
                    chunks.append(current_chunk)
                    # 保留重叠
                    if overlap > 0 and len(current_chunk) > overlap:
                        current_chunk = current_chunk[-overlap:] + "\n\n" + para
                    else:
                        current_chunk = para
                else:
                    current_chunk = (current_chunk + "\n\n" + para).strip()

                # 如果单个段落超长，按句子边界分割
                if len(current_chunk) > max_chunk_size:
                    sub_chunks = _split_by_sentences(current_chunk, max_chunk_size)
                    chunks.extend(sub_chunks[:-1])
                    current_chunk = sub_chunks[-1] if sub_chunks else ""

        # 保存最后一个块
        if current_chunk.strip() and len(current_chunk.strip()) >= min_chunk_size:
            chunks.append(current_chunk.strip())

    return chunks


def _split_by_sentences(text: str, max_size: int) -> List[str]:
    """按句子边界分割长文本"""
    # 中文句号、英文句号、分号、换行
    sentences = re.split(r'(?<=[。！？.!?\n;；])\s*', text)
    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) <= max_size:
            current += sent
        else:
            if current:
                chunks.append(current.strip())
            current = sent
    if current.strip():
        chunks.append(current.strip())
    return chunks


# ==================== 文档导入主流程 ====================

def import_document(filepath: str, knowledge_store,
                    category: str = "theory",
                    confidence: float = 0.95,
                    max_chunk_size: int = 800,
                    min_relevance: float = 0.3,
                    progress_callback: Optional[Callable[[int, int, str], None]] = None,
                    vision_recognizer=None
                    ) -> Dict[str, Any]:
    """
    将文档导入知识库

    参数:
        filepath: 文件路径（PDF/TXT/MD）
        knowledge_store: KnowledgeStore 实例
        category: 知识分类（默认 theory）
        confidence: 置信度（教材默认 0.95）
        max_chunk_size: 最大段落长度
        min_relevance: 最低相关度阈值（低于此值的段落跳过）
        progress_callback: 进度回调 fn(current, total, message)
        vision_recognizer: VisionRecognizer实例（可选，用于AI视觉识别）

    返回:
        导入统计信息
    """
    if not os.path.exists(filepath):
        return {"status": "error", "message": f"文件不存在: {filepath}"}

    # 1. 提取文本（含表格和图片识别）
    if progress_callback:
        msg = "正在提取文本"
        if vision_recognizer:
            msg += "（AI视觉识别已启用）"
        msg += "..."
        progress_callback(0, 100, msg)
    try:
        full_text, meta = extract_text(filepath, vision=vision_recognizer)
    except ImportError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:
        return {"status": "error", "message": f"文件读取失败: {e}"}

    if not full_text.strip():
        return {"status": "error", "message": "文件内容为空"}

    source_name = meta.get("title") or meta.get("filename", "未知文档")

    # 2. 智能分段
    if progress_callback:
        progress_callback(10, 100, "正在智能分段...")
    chunks = chunk_text(full_text, max_chunk_size=max_chunk_size)

    if not chunks:
        return {"status": "error", "message": "未能从文档中提取有效段落"}

    # 3. 过滤和导入
    imported = 0
    skipped_low_relevance = 0
    skipped_duplicate = 0
    total = len(chunks)

    for i, chunk in enumerate(chunks):
        if progress_callback:
            pct = 10 + int(85 * (i + 1) / total)
            progress_callback(pct, 100, f"正在导入 {i + 1}/{total} ...")

        # 检查相关度
        relevance = _compute_relevance(chunk)
        if relevance < min_relevance:
            skipped_low_relevance += 1
            continue

        # 生成主题和标签
        topic = _generate_topic(chunk, i, source_name)
        tags = _extract_tags(chunk)

        # 写入知识库
        result = knowledge_store.add_knowledge(
            topic=topic,
            content=chunk,
            category=category,
            source=f"文档: {source_name}",
            confidence=confidence,
            tags=tags
        )

        if result.get("status") == "exists":
            skipped_duplicate += 1
        else:
            imported += 1

    if progress_callback:
        progress_callback(100, 100, "导入完成")

    return {
        "status": "success",
        "message": (f"文档《{source_name}》导入完成"),
        "source": source_name,
        "total_chunks": total,
        "imported": imported,
        "skipped_low_relevance": skipped_low_relevance,
        "skipped_duplicate": skipped_duplicate,
        "pages": meta.get("pages", 0),
        "tables_extracted": meta.get("tables_extracted", 0),
        "images_processed": meta.get("images_processed", 0),
        "ocr_available": meta.get("ocr_available", False),
        "ai_vision": meta.get("ai_vision", False),
    }
