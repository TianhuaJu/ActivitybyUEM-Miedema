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

def extract_text_from_pdf(filepath: str) -> Tuple[str, Dict[str, Any]]:
    """
    从PDF文件提取全文

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

    full_text = []
    for page in doc:
        text = page.get_text("text")
        if text.strip():
            full_text.append(text)

    doc.close()
    return "\n\n".join(full_text), meta


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


def extract_text(filepath: str) -> Tuple[str, Dict[str, Any]]:
    """根据文件扩展名选择提取方法"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
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
                    progress_callback: Optional[Callable[[int, int, str], None]] = None
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

    返回:
        导入统计信息
    """
    if not os.path.exists(filepath):
        return {"status": "error", "message": f"文件不存在: {filepath}"}

    # 1. 提取文本
    if progress_callback:
        progress_callback(0, 100, "正在提取文本...")
    try:
        full_text, meta = extract_text(filepath)
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
    }
