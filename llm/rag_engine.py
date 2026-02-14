# -*- coding: utf-8 -*-
"""
RAG Engine - 检索增强生成引擎
=============================
自动从知识库中检索与用户查询相关的领域知识，
注入对话上下文，提升回答的准确性和专业深度。
"""

import re
from typing import List, Tuple


# 冶金热力学领域术语及同义词
_DOMAIN_TERMS = {
    "活度": ["activity", "活度系数", "γ", "拉乌尔"],
    "焓": ["enthalpy", "混合焓", "生成焓", "ΔH", "放热", "吸热"],
    "熵": ["entropy", "ΔS", "混合熵"],
    "吉布斯": ["gibbs", "自由能", "ΔG", "gibbs能"],
    "化学势": ["chemical potential", "μ", "偏摩尔"],
    "液相线": ["liquidus", "熔点", "凝固", "凝固点"],
    "析出": ["precipitation", "析出温度", "溶解度", "固溶"],
    "交互作用": ["interaction", "ε", "相互作用", "交互系数"],
    "外推": ["extrapolation", "UEM", "muggianu", "toop", "kohler"],
    "相图": ["phase diagram", "相平衡", "相稳定性", "相变"],
    "合金": ["alloy", "二元", "三元", "多元", "多组元"],
    "熔体": ["melt", "液态", "液相", "熔融"],
    "渣": ["slag", "熔渣", "炉渣", "造渣"],
    "wagner": ["瓦格纳", "一阶"],
    "miedema": ["米迪马", "半经验"],
    "calphad": ["相图计算", "计算相图"],
    "darken": ["达肯", "二阶"],
    "elliott": ["二阶交叉"],
    "脱氧": ["deoxidation", "脱氧平衡", "氧含量"],
    "脱硫": ["desulfurization", "脱硫平衡", "硫含量"],
    "标准态": ["standard state", "参考态", "纯物质"],
    "亨利": ["henry", "亨利定律", "稀溶液"],
}

# 元素符号
_ELEMENT_RE = re.compile(
    r'\b(H|He|Li|Be|B|C|N|O|F|Ne|Na|Mg|Al|Si|P|S|Cl|Ar|K|Ca|'
    r'Sc|Ti|V|Cr|Mn|Fe|Co|Ni|Cu|Zn|Ga|Ge|As|Se|Br|Kr|'
    r'Rb|Sr|Y|Zr|Nb|Mo|Ru|Rh|Pd|Ag|Cd|In|Sn|Sb|Te|'
    r'Cs|Ba|La|Ce|Pr|Nd|Sm|Eu|Gd|Tb|Dy|Ho|Er|Tm|Yb|Lu|'
    r'Hf|Ta|W|Re|Os|Ir|Pt|Au|Hg|Tl|Pb|Bi|U)\b'
)


class RAGEngine:
    """检索增强生成引擎 — 为对话自动注入相关领域知识"""

    def __init__(self, knowledge_store):
        """
        参数:
            knowledge_store: KnowledgeStore 实例
        """
        self.store = knowledge_store

    def retrieve(self, query: str, top_k: int = 5) -> str:
        """
        根据用户查询检索相关知识，返回格式化的参考上下文。

        参数:
            query: 用户查询文本
            top_k: 最多返回的条目数

        返回:
            格式化的参考上下文字符串，无结果时返回空串
        """
        keywords = self._extract_keywords(query)
        if not keywords:
            return ""

        # 用各关键词搜索，去重
        seen_ids = set()
        scored = []
        for kw in keywords:
            entries = self.store.search_knowledge(kw, limit=20)
            for entry in entries:
                if entry.id not in seen_ids:
                    seen_ids.add(entry.id)
                    score = self._score(entry, keywords)
                    scored.append((score, entry))

        if not scored:
            return ""

        scored.sort(key=lambda x: x[0], reverse=True)
        top = [e for _, e in scored[:top_k]]

        # 标记已访问
        for e in top:
            try:
                self.store.increment_access(e.id)
            except Exception:
                pass

        return self._format(top)

    def retrieve_user_data(self, query: str) -> str:
        """
        根据查询检索相关的用户实验数据。

        参数:
            query: 用户查询文本

        返回:
            格式化的实验数据参考，无结果时返回空串
        """
        elements = _ELEMENT_RE.findall(query)
        if not elements:
            return ""

        results = []
        seen = set()
        for el in elements:
            for dtype in ["first_order", "second_order", "lnY0", "enthalpy"]:
                entries = self.store.query_user_data(
                    data_type=dtype, solvent=el
                )
                for e in entries:
                    key = (e.data_type, e.solvent, e.solute_i, e.solute_j, e.value_type)
                    if key not in seen:
                        seen.add(key)
                        results.append(e)
            # 也搜索 solute_i
            for dtype in ["first_order", "second_order", "lnY0"]:
                entries = self.store.query_user_data(
                    data_type=dtype, solute_i=el
                )
                for e in entries:
                    key = (e.data_type, e.solvent, e.solute_i, e.solute_j, e.value_type)
                    if key not in seen:
                        seen.add(key)
                        results.append(e)

        if not results:
            return ""

        lines = ["[检索到的相关实验数据]"]
        for e in results[:10]:
            desc = f"{e.solvent}中 {e.solute_i}"
            if e.solute_j:
                desc += f"/{e.solute_j}"
            desc += f" {e.value_type}={e.value}"
            if e.temperature:
                desc += f" (T={e.temperature}K)"
            if e.reference:
                desc += f" 来源:{e.reference}"
            lines.append(f"  - {desc}")
        return "\n".join(lines)

    # ---- 内部方法 ----

    def _extract_keywords(self, query: str) -> List[str]:
        """从查询中提取检索关键词"""
        keywords = []

        # 1. 元素符号
        keywords.extend(_ELEMENT_RE.findall(query))

        # 2. 领域术语匹配
        q_lower = query.lower()
        for term, synonyms in _DOMAIN_TERMS.items():
            if term in q_lower:
                keywords.append(term)
            else:
                for syn in synonyms:
                    if syn.lower() in q_lower:
                        keywords.append(term)
                        break

        # 3. 中文关键短语（连续汉字 ≥2字）
        chinese = re.sub(r'[^\u4e00-\u9fff]', ' ', query)
        for seg in chinese.split():
            if 2 <= len(seg) <= 6:
                keywords.append(seg)

        return list(set(keywords))

    def _score(self, entry, keywords: List[str]) -> float:
        """计算知识条目与查询的相关度得分"""
        score = 0.0
        text = f"{entry.topic} {entry.content} {entry.tags}".lower()

        for kw in keywords:
            kw_l = kw.lower()
            if kw_l in entry.topic.lower():
                score += 3.0
            if kw_l in (entry.tags or "").lower():
                score += 2.0
            if kw_l in entry.content.lower():
                score += 1.0

        # 置信度加权
        score *= (0.5 + entry.confidence * 0.5)
        # 访问频率微调
        score += min(entry.access_count * 0.1, 1.0)

        return score

    def _format(self, entries) -> str:
        """格式化检索结果"""
        _CAT = {
            "theory": "理论", "formula": "公式",
            "experimental": "实验", "experience": "经验",
            "correction": "修正", "general": "通用",
        }
        lines = ["[检索到的相关领域知识]"]
        for i, e in enumerate(entries, 1):
            cat = _CAT.get(e.category, e.category)
            lines.append(f"{i}. [{cat}] {e.topic}: {e.content}")
        return "\n".join(lines)
