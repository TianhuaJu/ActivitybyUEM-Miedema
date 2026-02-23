# -*- coding: utf-8 -*-
"""
AsyncTaskQueue - 异步任务队列
==============================
管理长时间运行的计算任务（DFT、MD等），提供提交、轮询、取消等操作。
任务状态持久化到 SQLite，支持应用重启后恢复。
"""

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    plugin_name: str
    tool_name: str
    arguments: Dict[str, Any]
    status: TaskStatus
    progress: float = 0.0              # 0.0 ~ 1.0
    message: str = ""
    created_at: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转为可序列化的字典"""
        d = {
            "task_id": self.task_id,
            "plugin_name": self.plugin_name,
            "tool_name": self.tool_name,
            "status": self.status.value,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }
        if self.result is not None:
            d["result"] = self.result
        if self.error is not None:
            d["error"] = self.error
        return d


class AsyncTaskQueue:
    """
    异步任务队列。

    使用 ThreadPoolExecutor 执行长时间计算，
    SQLite 持久化任务状态，支持应用重启后查询历史任务。
    """

    _MAX_QUEUE_SIZE = 100     # 最大并存任务数
    _CLEANUP_DAYS = 7         # 超过此天数的已完成任务自动清理

    def __init__(self, db_path: str = None, max_workers: int = 4):
        """
        参数:
            db_path: SQLite 数据库路径，默认 ~/.alloyact/tasks.db
            max_workers: 最大并行工作线程数
        """
        self._db_path = db_path or os.path.join(
            os.path.expanduser("~/.alloyact"), "tasks.db"
        )
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="async_task"
        )
        self._tasks: Dict[str, TaskInfo] = {}
        self._futures: Dict[str, Future] = {}
        self._lock = threading.Lock()
        self._init_db()
        self._load_history()

    # ==================== 公开接口 ====================

    def submit(self, plugin_name: str, tool_name: str,
               arguments: Dict[str, Any],
               execute_fn=None) -> str:
        """
        提交异步任务。

        参数:
            plugin_name: 插件名称
            tool_name: 工具名称
            arguments: 工具参数
            execute_fn: 可调用对象 (tool_name, arguments) -> Dict

        返回:
            task_id
        """
        with self._lock:
            active = sum(
                1 for t in self._tasks.values()
                if t.status in (TaskStatus.PENDING, TaskStatus.RUNNING)
            )
            if active >= self._MAX_QUEUE_SIZE:
                raise RuntimeError(
                    f"任务队列已满（{active}/{self._MAX_QUEUE_SIZE}），"
                    "请等待部分任务完成后再提交"
                )

        task_id = str(uuid.uuid4())[:12]
        now = time.time()
        info = TaskInfo(
            task_id=task_id,
            plugin_name=plugin_name,
            tool_name=tool_name,
            arguments=arguments,
            status=TaskStatus.PENDING,
            message="任务已提交，等待执行",
            created_at=now,
        )

        with self._lock:
            self._tasks[task_id] = info
            self._save_task(info)

        if execute_fn is not None:
            future = self._executor.submit(
                self._run_task, task_id, execute_fn, tool_name, arguments
            )
            self._futures[task_id] = future

        return task_id

    def poll(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态。

        返回:
            TaskInfo.to_dict() 或 error dict
        """
        info = self._tasks.get(task_id)
        if not info:
            return {"status": "error", "message": f"任务不存在: {task_id}"}
        return info.to_dict()

    def get_result(self, task_id: str) -> Dict[str, Any]:
        """获取已完成任务的结果"""
        info = self._tasks.get(task_id)
        if not info:
            return {"status": "error", "message": f"任务不存在: {task_id}"}
        if info.status == TaskStatus.COMPLETED:
            return info.result or {"status": "success", "message": "任务已完成，无返回数据"}
        if info.status == TaskStatus.FAILED:
            return {"status": "error", "message": info.error or "任务失败"}
        return {
            "status": "error",
            "message": f"任务尚未完成 (当前状态: {info.status.value}，进度: {info.progress:.0%})",
        }

    def cancel(self, task_id: str) -> Dict[str, Any]:
        """取消任务"""
        info = self._tasks.get(task_id)
        if not info:
            return {"status": "error", "message": f"任务不存在: {task_id}"}

        if info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            return {"status": "error",
                    "message": f"任务已处于终态: {info.status.value}"}

        future = self._futures.get(task_id)
        if future and not future.done():
            future.cancel()

        with self._lock:
            info.status = TaskStatus.CANCELLED
            info.completed_at = time.time()
            info.message = "任务已取消"
            self._save_task(info)

        return {"status": "success", "message": "任务已取消"}

    def list_tasks(self, status: TaskStatus = None,
                   limit: int = 20) -> List[Dict[str, Any]]:
        """
        列出任务。

        参数:
            status: 可选状态过滤
            limit: 最大返回数
        """
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        return [t.to_dict() for t in tasks[:limit]]

    def update_progress(self, task_id: str, progress: float,
                        message: str = "") -> None:
        """更新任务进度（供插件内部回调使用）"""
        info = self._tasks.get(task_id)
        if info and info.status == TaskStatus.RUNNING:
            info.progress = max(0.0, min(1.0, progress))
            if message:
                info.message = message

    def cleanup(self, days: int = None) -> int:
        """清理超期的已完成任务"""
        days = days or self._CLEANUP_DAYS
        cutoff = time.time() - days * 86400
        to_remove = []
        for tid, info in self._tasks.items():
            if (info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED,
                                TaskStatus.CANCELLED)
                    and info.completed_at and info.completed_at < cutoff):
                to_remove.append(tid)

        for tid in to_remove:
            del self._tasks[tid]
            self._delete_task(tid)

        return len(to_remove)

    def shutdown(self) -> None:
        """关闭线程池"""
        self._executor.shutdown(wait=False)

    # ==================== 内部方法 ====================

    def _run_task(self, task_id: str, execute_fn,
                  tool_name: str, arguments: Dict[str, Any]) -> None:
        """在工作线程中执行任务"""
        info = self._tasks.get(task_id)
        if not info:
            return

        with self._lock:
            info.status = TaskStatus.RUNNING
            info.started_at = time.time()
            info.message = "正在执行"
            self._save_task(info)

        try:
            result = execute_fn(tool_name, arguments)
            with self._lock:
                info.status = TaskStatus.COMPLETED
                info.progress = 1.0
                info.completed_at = time.time()
                info.result = result
                info.message = "执行完成"
                self._save_task(info)
        except Exception as e:
            with self._lock:
                info.status = TaskStatus.FAILED
                info.completed_at = time.time()
                info.error = str(e)
                info.message = f"执行失败: {e}"
                self._save_task(info)
            logger.error("异步任务 %s 执行失败: %s", task_id, e)

    # ==================== SQLite 持久化 ====================

    def _init_db(self) -> None:
        """初始化数据库表"""
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    plugin_name TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments TEXT,
                    status TEXT NOT NULL,
                    progress REAL DEFAULT 0,
                    message TEXT DEFAULT '',
                    created_at REAL,
                    started_at REAL,
                    completed_at REAL,
                    result TEXT,
                    error TEXT
                )
            """)
            conn.commit()

    def _save_task(self, info: TaskInfo) -> None:
        """保存/更新任务到数据库"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tasks
                    (task_id, plugin_name, tool_name, arguments, status,
                     progress, message, created_at, started_at, completed_at,
                     result, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    info.task_id, info.plugin_name, info.tool_name,
                    json.dumps(info.arguments, ensure_ascii=False),
                    info.status.value, info.progress, info.message,
                    info.created_at, info.started_at, info.completed_at,
                    json.dumps(info.result, ensure_ascii=False) if info.result else None,
                    info.error,
                ))
                conn.commit()
        except Exception:
            logger.warning("保存任务状态失败: %s", info.task_id, exc_info=True)

    def _delete_task(self, task_id: str) -> None:
        """从数据库删除任务"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
                conn.commit()
        except Exception:
            logger.warning("删除任务失败: %s", task_id, exc_info=True)

    def _load_history(self) -> None:
        """从数据库恢复任务历史（仅已完成的任务）"""
        try:
            with sqlite3.connect(self._db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 50"
                ).fetchall()
                for row in rows:
                    info = TaskInfo(
                        task_id=row[0],
                        plugin_name=row[1],
                        tool_name=row[2],
                        arguments=json.loads(row[3]) if row[3] else {},
                        status=TaskStatus(row[4]),
                        progress=row[5] or 0.0,
                        message=row[6] or "",
                        created_at=row[7] or 0.0,
                        started_at=row[8],
                        completed_at=row[9],
                        result=json.loads(row[10]) if row[10] else None,
                        error=row[11],
                    )
                    # 将中断的运行中任务标记为失败
                    if info.status in (TaskStatus.PENDING, TaskStatus.RUNNING):
                        info.status = TaskStatus.FAILED
                        info.error = "应用重启，任务被中断"
                        info.completed_at = time.time()
                        self._save_task(info)
                    self._tasks[info.task_id] = info
        except Exception:
            logger.warning("加载任务历史失败", exc_info=True)
