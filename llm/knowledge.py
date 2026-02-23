# -*- coding: utf-8 -*-
"""
Knowledge Store - AI助手进化式知识库
====================================
基于SQLite的持久知识存储，支持：
1. 领域知识积累 — 从对话中提取并存储材料/冶金/热力学知识
2. 实验数据管理 — 存储用户提供的实验值，可覆盖默认数据库
3. 知识检索与注入 — 将相关知识注入系统提示词，使AI越来越聪明
"""

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

DEFAULT_KNOWLEDGE_DIR = os.path.join(os.path.expanduser("~"), ".alloyact")
DEFAULT_KNOWLEDGE_DB = os.path.join(DEFAULT_KNOWLEDGE_DIR, "knowledge.db")


@dataclass
class KnowledgeEntry:
    """一条知识"""
    id: int = 0
    topic: str = ""           # 主题（如"Fe-C体系活度系数"）
    content: str = ""         # 知识内容
    category: str = "general" # 分类: theory/formula/experimental/experience/correction
    source: str = ""          # 来源（对话/论文/用户手动）
    confidence: float = 0.8   # 置信度 0-1
    tags: str = ""            # 标签（逗号分隔，如"Fe,C,活度"）
    created_at: float = 0
    updated_at: float = 0
    access_count: int = 0


@dataclass
class UserDataEntry:
    """用户提供的实验数据"""
    id: int = 0
    data_type: str = ""       # 数据类型: first_order/lnY0/second_order/enthalpy
    solvent: str = ""         # 基体元素
    solute_i: str = ""        # 溶质i
    solute_j: str = ""        # 溶质j（可选）
    value: float = 0.0        # 数值
    value_type: str = ""      # 值类型: eji/sji/lnYi0/Yi0/ri_ij/pi_ij 等
    temperature: str = ""     # 温度（K）或温度公式
    reference: str = ""       # 来源/文献
    note: str = ""            # 备注
    created_at: float = 0
    is_active: int = 1        # 是否启用（1=启用，0=禁用）


class KnowledgeStore:
    """
    进化式知识库

    使用示例:
    ```python
    store = KnowledgeStore()

    # 存储领域知识
    store.add_knowledge(
        topic="Fe-C体系相互作用系数温度依赖性",
        content="Fe-C体系一阶活度相互作用系数ε_C^C在1823-1923K范围内约为0.14，随温度升高略有增大",
        category="experience",
        tags="Fe,C,相互作用系数,温度"
    )

    # 存储实验数据
    store.add_user_data(
        data_type="first_order",
        solvent="Fe", solute_i="C", solute_j="Si",
        value=0.08, value_type="eji",
        temperature="1873", reference="Zhang et al. 2024"
    )
    ```
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DEFAULT_KNOWLEDGE_DB
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """初始化知识库表结构"""
        conn = self._get_conn()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    source TEXT DEFAULT '',
                    confidence REAL DEFAULT 0.8,
                    tags TEXT DEFAULT '',
                    created_at REAL,
                    updated_at REAL,
                    access_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS user_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_type TEXT NOT NULL,
                    solvent TEXT DEFAULT '',
                    solute_i TEXT DEFAULT '',
                    solute_j TEXT DEFAULT '',
                    value REAL,
                    value_type TEXT DEFAULT '',
                    temperature TEXT DEFAULT '',
                    reference TEXT DEFAULT '',
                    note TEXT DEFAULT '',
                    created_at REAL,
                    is_active INTEGER DEFAULT 1
                );

                CREATE INDEX IF NOT EXISTS idx_knowledge_category
                    ON knowledge(category);
                CREATE INDEX IF NOT EXISTS idx_knowledge_tags
                    ON knowledge(tags);
                CREATE INDEX IF NOT EXISTS idx_user_data_type
                    ON user_data(data_type, solvent, solute_i, solute_j);
            """)
            conn.commit()
        finally:
            conn.close()

    # ==================== 知识管理 ====================

    @staticmethod
    def _tokenize(text: str) -> set:
        """对文本进行分词，返回词元集合（中英文混合分词）"""
        # 英文单词
        words = set(re.findall(r'[a-zA-Z][a-zA-Z0-9]*', text.lower()))
        # 中文：按2-gram切分
        chinese = re.findall(r'[\u4e00-\u9fff]+', text)
        for seg in chinese:
            for i in range(len(seg) - 1):
                words.add(seg[i:i+2])
            if len(seg) == 1:
                words.add(seg)
        # 元素符号（大写开头）
        words.update(re.findall(r'[A-Z][a-z]?', text))
        return words

    @staticmethod
    def _jaccard_similarity(set_a: set, set_b: set) -> float:
        """计算Jaccard相似度"""
        if not set_a or not set_b:
            return 0.0
        intersection = set_a & set_b
        union = set_a | set_b
        return len(intersection) / len(union)

    def find_similar_knowledge(self, topic: str, content: str,
                               threshold: float = 0.6) -> List[Tuple[KnowledgeEntry, float]]:
        """
        基于关键词重叠的相似度搜索

        参数:
            topic: 主题
            content: 内容
            threshold: 相似度阈值（0-1）
        返回:
            [(知识条目, 相似度), ...] 按相似度降序
        """
        query_tokens = self._tokenize(topic + " " + content)
        all_entries = self.get_all_knowledge()
        similar = []
        for entry in all_entries:
            entry_tokens = self._tokenize(entry.topic + " " + entry.content)
            sim = self._jaccard_similarity(query_tokens, entry_tokens)
            if sim >= threshold:
                similar.append((entry, sim))
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar

    def merge_knowledge(self, source_ids: List[int], merged_topic: str,
                        merged_content: str, category: str = "general",
                        confidence: float = 0.8) -> Dict[str, Any]:
        """
        合并多条知识为一条

        参数:
            source_ids: 要合并的知识ID列表
            merged_topic: 合并后的主题
            merged_content: 合并后的内容
            category: 分类
            confidence: 置信度
        返回:
            操作结果
        """
        conn = self._get_conn()
        try:
            # 获取旧条目信息用于累计
            placeholders = ",".join("?" * len(source_ids))
            rows = conn.execute(
                f"SELECT id, tags, access_count, confidence FROM knowledge WHERE id IN ({placeholders})",
                source_ids
            ).fetchall()
            if not rows:
                return {"status": "error", "message": "未找到指定的知识条目"}

            max_access = max(r[2] for r in rows)
            max_conf = max(r[3] for r in rows)
            all_tags = set()
            for r in rows:
                if r[1]:
                    all_tags.update(t.strip() for t in r[1].split(",") if t.strip())
            merged_tags = ",".join(sorted(all_tags))

            # 删除旧条目
            conn.execute(
                f"DELETE FROM knowledge WHERE id IN ({placeholders})",
                source_ids
            )

            # 插入合并后的条目
            now = time.time()
            conn.execute(
                """INSERT INTO knowledge
                   (topic, content, category, source, confidence, tags,
                    created_at, updated_at, access_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (merged_topic, merged_content, category, "知识库优化合并",
                 max(confidence, max_conf), merged_tags, now, now, max_access)
            )
            conn.commit()
            return {
                "status": "success",
                "message": f"已合并 {len(source_ids)} 条知识为: {merged_topic}",
                "merged_count": len(source_ids)
            }
        finally:
            conn.close()

    def add_knowledge(self, topic: str, content: str, category: str = "general",
                      source: str = "", confidence: float = 0.8,
                      tags: str = "") -> Dict[str, Any]:
        """
        添加一条知识（含相似度检测和自动合并）

        参数:
            topic: 主题
            content: 知识内容
            category: 分类 (theory/formula/experimental/experience/correction/general)
            source: 来源
            confidence: 置信度 0-1
            tags: 标签（逗号分隔）
        """
        # 精确匹配去重
        existing = self.search_knowledge(topic, limit=5)
        for entry in existing:
            if entry.content == content:
                return {"status": "exists", "message": f"已存在相同知识: {topic}"}

        # 相似度检测
        similar = self.find_similar_knowledge(topic, content, threshold=0.5)
        hint_msg = ""

        if similar:
            best_entry, best_sim = similar[0]
            if best_sim > 0.8:
                # 高度相似：自动合并（取较新内容，累计access_count，取较高confidence）
                conn = self._get_conn()
                try:
                    new_conf = max(confidence, best_entry.confidence)
                    new_access = best_entry.access_count + 1
                    # 合并标签
                    old_tags = set(t.strip() for t in best_entry.tags.split(",") if t.strip())
                    new_tags = set(t.strip() for t in tags.split(",") if t.strip())
                    merged_tags = ",".join(sorted(old_tags | new_tags))
                    now = time.time()
                    conn.execute(
                        """UPDATE knowledge SET content=?, confidence=?, tags=?,
                           updated_at=?, access_count=?, source=?
                           WHERE id=?""",
                        (content, new_conf, merged_tags, now, new_access,
                         source or best_entry.source, best_entry.id)
                    )
                    conn.commit()
                    return {
                        "status": "success",
                        "message": f"已与相似知识合并更新: {best_entry.topic} (相似度{best_sim:.0%})",
                        "merged_with": best_entry.id
                    }
                finally:
                    conn.close()
            else:
                # 中度相似(0.5-0.8)：提示但仍保存
                hint_msg = f" (注意：与已有知识「{best_entry.topic}」相似度{best_sim:.0%})"

        now = time.time()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO knowledge
                   (topic, content, category, source, confidence, tags, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (topic, content, category, source, confidence, tags, now, now)
            )
            conn.commit()
            return {"status": "success", "message": f"已学习: {topic}{hint_msg}"}
        finally:
            conn.close()

    def search_knowledge(self, keyword: str = "", category: str = "",
                         limit: int = 20) -> List[KnowledgeEntry]:
        """搜索知识"""
        conn = self._get_conn()
        try:
            conditions = []
            params = []

            if keyword:
                conditions.append(
                    "(topic LIKE ? OR content LIKE ? OR tags LIKE ?)")
                kw = f"%{keyword}%"
                params.extend([kw, kw, kw])

            if category:
                conditions.append("category = ?")
                params.append(category)

            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            query = f"""SELECT id, topic, content, category, source, confidence,
                        tags, created_at, updated_at, access_count
                        FROM knowledge {where}
                        ORDER BY confidence DESC, updated_at DESC
                        LIMIT ?"""
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            entries = []
            for row in rows:
                entries.append(KnowledgeEntry(
                    id=row[0], topic=row[1], content=row[2],
                    category=row[3], source=row[4], confidence=row[5],
                    tags=row[6], created_at=row[7], updated_at=row[8],
                    access_count=row[9]
                ))
            return entries
        finally:
            conn.close()

    def get_all_knowledge(self) -> List[KnowledgeEntry]:
        """获取所有知识"""
        return self.search_knowledge(limit=1000)

    def update_knowledge(self, knowledge_id: int, content: str = None,
                         confidence: float = None, tags: str = None) -> Dict[str, Any]:
        """更新知识"""
        conn = self._get_conn()
        try:
            updates = ["updated_at = ?"]
            params = [time.time()]

            if content is not None:
                updates.append("content = ?")
                params.append(content)
            if confidence is not None:
                updates.append("confidence = ?")
                params.append(confidence)
            if tags is not None:
                updates.append("tags = ?")
                params.append(tags)

            params.append(knowledge_id)
            conn.execute(
                f"UPDATE knowledge SET {', '.join(updates)} WHERE id = ?",
                params
            )
            conn.commit()
            return {"status": "success", "message": "知识已更新"}
        finally:
            conn.close()

    def delete_knowledge(self, knowledge_id: int) -> Dict[str, Any]:
        """删除知识"""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM knowledge WHERE id = ?", (knowledge_id,))
            conn.commit()
            return {"status": "success", "message": "知识已删除"}
        finally:
            conn.close()

    def increment_access(self, knowledge_id: int):
        """增加知识的访问计数"""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE knowledge SET access_count = access_count + 1 WHERE id = ?",
                (knowledge_id,)
            )
            conn.commit()
        finally:
            conn.close()

    # ==================== 实验数据管理 ====================

    def add_user_data(self, data_type: str, solvent: str = "",
                      solute_i: str = "", solute_j: str = "",
                      value: float = 0.0, value_type: str = "",
                      temperature: str = "", reference: str = "",
                      note: str = "") -> Dict[str, Any]:
        """
        添加用户提供的实验数据

        参数:
            data_type: 数据类型 (first_order/lnY0/second_order/enthalpy)
            solvent: 基体元素
            solute_i: 溶质i
            solute_j: 溶质j（可选）
            value: 数值
            value_type: 值类型 (eji/sji/lnYi0/Yi0/ri_ij/pi_ij)
            temperature: 温度(K)或公式
            reference: 来源文献
            note: 备注
        """
        # 检查是否已有相同条目
        existing = self.query_user_data(data_type, solvent, solute_i, solute_j,
                                        value_type)
        if existing:
            # 更新已有数据
            conn = self._get_conn()
            try:
                conn.execute(
                    """UPDATE user_data SET value=?, temperature=?, reference=?,
                       note=?, is_active=1 WHERE id=?""",
                    (value, temperature, reference, note, existing[0].id)
                )
                conn.commit()
                return {
                    "status": "success",
                    "message": f"已更新 {solvent}中{solute_j}对{solute_i}的{value_type}: "
                               f"旧值={existing[0].value} → 新值={value}",
                    "action": "updated",
                    "old_value": existing[0].value,
                    "new_value": value
                }
            finally:
                conn.close()

        now = time.time()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO user_data
                   (data_type, solvent, solute_i, solute_j, value, value_type,
                    temperature, reference, note, created_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (data_type, solvent, solute_i, solute_j, value, value_type,
                 temperature, reference, note, now)
            )
            conn.commit()
            return {
                "status": "success",
                "message": f"已保存 {solvent}中{solute_j}对{solute_i}的{value_type}={value}"
                           f" (T={temperature}K, 来源: {reference})",
                "action": "created"
            }
        finally:
            conn.close()

    def query_user_data(self, data_type: str = "", solvent: str = "",
                        solute_i: str = "", solute_j: str = "",
                        value_type: str = "") -> List[UserDataEntry]:
        """查询用户实验数据"""
        conn = self._get_conn()
        try:
            conditions = ["is_active = 1"]
            params = []

            if data_type:
                conditions.append("data_type = ?")
                params.append(data_type)
            if solvent:
                conditions.append("solvent = ?")
                params.append(solvent)
            if solute_i:
                conditions.append("solute_i = ?")
                params.append(solute_i)
            if solute_j:
                conditions.append("solute_j = ?")
                params.append(solute_j)
            if value_type:
                conditions.append("value_type = ?")
                params.append(value_type)

            where = "WHERE " + " AND ".join(conditions)
            query = f"""SELECT id, data_type, solvent, solute_i, solute_j,
                        value, value_type, temperature, reference, note,
                        created_at, is_active
                        FROM user_data {where}
                        ORDER BY created_at DESC"""

            rows = conn.execute(query, params).fetchall()
            entries = []
            for row in rows:
                entries.append(UserDataEntry(
                    id=row[0], data_type=row[1], solvent=row[2],
                    solute_i=row[3], solute_j=row[4], value=row[5],
                    value_type=row[6], temperature=row[7], reference=row[8],
                    note=row[9], created_at=row[10], is_active=row[11]
                ))
            return entries
        finally:
            conn.close()

    def get_all_user_data(self) -> List[UserDataEntry]:
        """获取所有用户实验数据"""
        return self.query_user_data()

    def delete_user_data(self, data_id: int) -> Dict[str, Any]:
        """删除（禁用）一条实验数据"""
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE user_data SET is_active = 0 WHERE id = ?",
                (data_id,)
            )
            conn.commit()
            return {"status": "success", "message": "数据已删除"}
        finally:
            conn.close()

    # ==================== 提示词注入 ====================

    def format_knowledge_for_prompt(self, max_entries: int = 30) -> str:
        """
        将知识库内容格式化为系统提示词片段

        按置信度和访问频率排序，注入最相关的知识
        """
        entries = self.search_knowledge(limit=max_entries)
        if not entries:
            return ""

        categories = {
            "theory": "理论知识",
            "formula": "公式与模型",
            "experimental": "实验数据规律",
            "experience": "计算经验",
            "correction": "数据修正",
            "general": "其他知识",
        }

        grouped = {}
        for entry in entries:
            cat_name = categories.get(entry.category, entry.category)
            grouped.setdefault(cat_name, []).append(entry)

        lines = ["\n========== 已学习的领域知识（应在回答中参考） =========="]
        priority = ["理论知识", "公式与模型", "实验数据规律", "计算经验",
                     "数据修正", "其他知识"]
        for cat_name in priority:
            items = grouped.get(cat_name)
            if items:
                lines.append(f"【{cat_name}】")
                for item in items:
                    conf_tag = f"[置信度:{item.confidence:.0%}]" if item.confidence < 1.0 else ""
                    lines.append(f"  - {item.topic}: {item.content} {conf_tag}")

        return "\n".join(lines)

    def format_user_data_for_prompt(self) -> str:
        """将用户实验数据格式化为提示词片段"""
        entries = self.get_all_user_data()
        if not entries:
            return ""

        lines = ["\n========== 用户提供的实验数据（优先使用） =========="]
        lines.append("以下实验数据由用户提供，计算时应优先采用这些值：")

        for entry in entries:
            if entry.data_type == "first_order":
                lines.append(
                    f"  - {entry.solvent}中 ε_{{{entry.solute_i}}}^{{{entry.solute_j}}} = "
                    f"{entry.value} (T={entry.temperature}K, 来源: {entry.reference})"
                )
            elif entry.data_type == "lnY0":
                lines.append(
                    f"  - {entry.solvent}中 ln(γ°_{{{entry.solute_i}}}) = "
                    f"{entry.value} (T={entry.temperature}K, 来源: {entry.reference})"
                )
            elif entry.data_type == "second_order":
                lines.append(
                    f"  - {entry.solvent}中 {entry.value_type}_{{{entry.solute_i}}}^"
                    f"{{{entry.solute_j}}} = {entry.value} "
                    f"(T={entry.temperature}K, 来源: {entry.reference})"
                )
            else:
                lines.append(
                    f"  - {entry.data_type}: {entry.solute_i} {entry.value_type}="
                    f"{entry.value} (来源: {entry.reference})"
                )

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, int]:
        """获取知识库统计"""
        conn = self._get_conn()
        try:
            k_count = conn.execute(
                "SELECT COUNT(*) FROM knowledge").fetchone()[0]
            d_count = conn.execute(
                "SELECT COUNT(*) FROM user_data WHERE is_active = 1"
            ).fetchone()[0]
            return {"knowledge_count": k_count, "user_data_count": d_count}
        finally:
            conn.close()
