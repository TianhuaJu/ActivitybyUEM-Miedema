# -*- coding: utf-8 -*-
"""
Memory Store - AI助手持久记忆系统
================================
支持两种记忆：
1. 事实记忆 (facts) — 用户偏好、常用体系等，由LLM主动保存
2. 对话历史 (sessions) — 完整对话记录，自动保存/加载

作者: Claude
日期: 2026-02-12
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from pathlib import Path


# 默认存储目录
DEFAULT_MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".alloyact")


@dataclass
class Memory:
    """一条记忆"""
    content: str           # 记忆内容
    category: str          # 分类: preference/alloy_system/calculation/general
    timestamp: float = 0   # 创建时间戳
    source: str = ""       # 来源（哪次对话）

    def __post_init__(self):
        if self.timestamp == 0:
            self.timestamp = time.time()


class MemoryStore:
    """
    持久记忆存储

    使用示例:
    ```python
    store = MemoryStore()
    store.add("用户经常计算Fe-C-Si合金", "alloy_system")
    store.add("用户偏好UEM1外推模型", "preference")
    memories = store.get_all()
    ```
    """

    def __init__(self, memory_dir: str = None):
        self.memory_dir = memory_dir or DEFAULT_MEMORY_DIR
        self.memories_file = os.path.join(self.memory_dir, "memories.json")
        self.sessions_dir = os.path.join(self.memory_dir, "sessions")

        # 确保目录存在
        os.makedirs(self.memory_dir, exist_ok=True)
        os.makedirs(self.sessions_dir, exist_ok=True)

        # 加载已有记忆
        self.memories: List[Memory] = self._load_memories()

    def _load_memories(self) -> List[Memory]:
        """从文件加载记忆"""
        if not os.path.exists(self.memories_file):
            return []
        try:
            with open(self.memories_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return [Memory(**item) for item in data]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    def _save_memories(self):
        """保存记忆到文件"""
        data = [asdict(m) for m in self.memories]
        with open(self.memories_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(self, content: str, category: str = "general", source: str = "") -> str:
        """
        添加一条记忆

        参数:
            content: 记忆内容
            category: 分类 (preference/alloy_system/calculation/general)
            source: 来源描述
        返回:
            确认消息
        """
        # 检查是否已有相似记忆（避免重复）
        for existing in self.memories:
            if existing.content == content:
                return f"已存在相同记忆: {content}"

        memory = Memory(content=content, category=category, source=source)
        self.memories.append(memory)
        self._save_memories()
        return f"已记住: {content}"

    def get_all(self) -> List[Memory]:
        """获取所有记忆"""
        return list(self.memories)

    def get_by_category(self, category: str) -> List[Memory]:
        """按分类获取记忆"""
        return [m for m in self.memories if m.category == category]

    def search(self, keyword: str) -> List[Memory]:
        """按关键词搜索记忆"""
        keyword = keyword.lower()
        return [m for m in self.memories if keyword in m.content.lower()]

    def remove(self, content: str) -> str:
        """删除指定记忆"""
        before = len(self.memories)
        self.memories = [m for m in self.memories if m.content != content]
        if len(self.memories) < before:
            self._save_memories()
            return f"已删除: {content}"
        return f"未找到: {content}"

    def clear_all(self) -> str:
        """清除所有记忆"""
        self.memories = []
        self._save_memories()
        return "已清除所有记忆"

    def format_for_prompt(self) -> str:
        """将记忆格式化为系统提示的一部分"""
        if not self.memories:
            return ""

        categories = {
            "preference": "用户偏好",
            "alloy_system": "常用合金体系",
            "calculation": "计算经验",
            "general": "其他"
        }

        lines = ["\n你记得以下关于用户的信息："]
        grouped = {}
        for m in self.memories:
            cat = categories.get(m.category, m.category)
            grouped.setdefault(cat, []).append(m.content)

        for cat_name, items in grouped.items():
            lines.append(f"【{cat_name}】")
            for item in items:
                lines.append(f"  - {item}")

        return "\n".join(lines)

    # ============= 对话历史持久化 =============

    def save_session(self, messages: List[Dict], session_id: str = None) -> str:
        """
        保存对话历史

        参数:
            messages: 消息列表 [{"role": ..., "content": ...}, ...]
            session_id: 会话ID（默认用时间戳）
        返回:
            保存的文件路径
        """
        if session_id is None:
            session_id = time.strftime("%Y%m%d_%H%M%S")

        filepath = os.path.join(self.sessions_dir, f"{session_id}.json")
        data = {
            "session_id": session_id,
            "timestamp": time.time(),
            "message_count": len(messages),
            "messages": messages
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    def load_session(self, session_id: str) -> Optional[List[Dict]]:
        """加载指定对话历史"""
        filepath = os.path.join(self.sessions_dir, f"{session_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("messages", [])
        except (json.JSONDecodeError, TypeError):
            return None

    def load_latest_session(self) -> Optional[List[Dict]]:
        """加载最近一次对话历史"""
        sessions = self.list_sessions()
        if not sessions:
            return None
        latest = sessions[0]
        return self.load_session(latest["session_id"])

    def list_sessions(self) -> List[Dict]:
        """列出所有保存的会话（按时间倒序）"""
        sessions = []
        for f in Path(self.sessions_dir).glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                sessions.append({
                    "session_id": data.get("session_id", f.stem),
                    "timestamp": data.get("timestamp", 0),
                    "message_count": data.get("message_count", 0),
                    "file": str(f)
                })
            except (json.JSONDecodeError, TypeError):
                continue
        sessions.sort(key=lambda s: s["timestamp"], reverse=True)
        return sessions

    def get_recent_summary(self, max_sessions: int = 3) -> str:
        """获取最近几次对话的摘要（注入到提示词中）"""
        sessions = self.list_sessions()[:max_sessions]
        if not sessions:
            return ""

        lines = ["\n最近的计算历史："]
        for sess in sessions:
            msgs = self.load_session(sess["session_id"])
            if not msgs:
                continue
            ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(sess["timestamp"]))
            # 提取用户问题摘要
            user_msgs = [m["content"][:80] for m in msgs
                        if m.get("role") == "user" and m.get("content")]
            if user_msgs:
                lines.append(f"  [{ts}] {'; '.join(user_msgs[:3])}")

        return "\n".join(lines) if len(lines) > 1 else ""
