#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务模型 — 批量队列 · 并发控制 · 持久化
"""
import json
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

from .engine import Base64Engine

logger = logging.getLogger(__name__)

# 存储目录
_APP_DIR = os.path.join(os.path.expanduser("~"), ".base64_converter")
try:
    os.makedirs(_APP_DIR, exist_ok=True)
except Exception:
    pass

_QUEUE_FILE = os.path.join(_APP_DIR, "queue.json")


@dataclass
class QueueTask:
    """单个队列任务"""
    tid: str
    mode: str                    # "encode" | "decode"
    input_path: str
    output_path: str
    options: dict = field(default_factory=dict)
    status: str = "pending"      # pending | running | completed | failed | cancelled
    progress: float = 0.0
    error: str = ""
    result: Optional[dict] = None
    cancel_event: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> dict:
        return {
            "tid": self.tid, "mode": self.mode,
            "input_path": self.input_path, "output_path": self.output_path,
            "options": self.options, "status": self.status,
            "progress": self.progress, "error": self.error, "result": self.result,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "QueueTask":
        return cls(
            tid=d["tid"], mode=d["mode"],
            input_path=d["input_path"], output_path=d["output_path"],
            options=d.get("options", {}),
            status=d.get("status", "pending"),
            progress=d.get("progress", 0.0),
            error=d.get("error", ""),
            result=d.get("result"),
        )


class BatchExecutor:
    """批量任务执行器 — 并发控制 · 进度回调 · 取消支持 · 持久化"""

    def __init__(self, app, max_concurrent: int = 2):
        """
        Args:
            app: 持有 _safe_after(ms, func), refresh_queue(), _update_task_progress()
                 和 _set_status(text, color) 方法的对象
            max_concurrent: 最大并发数
        """
        self.app = app
        self.max_concurrent = max_concurrent
        self.tasks: List[QueueTask] = []
        self.lock = threading.Lock()
        self._running = False
        self._stop_requested = False
        self._worker_thread: Optional[threading.Thread] = None
        # 加载持久化任务
        self._load_queue()

    def set_max_concurrent(self, n: int):
        with self.lock:
            self.max_concurrent = max(1, min(8, n))

    def add_task(self, task: QueueTask) -> None:
        with self.lock:
            self.tasks.append(task)
        self._safe_after(0, lambda: self._refresh_queue())
        logger.info(f"任务加入队列: {task.tid} {task.input_path}")
        self._save_queue()

    def add_tasks(self, tasks: List[QueueTask]) -> None:
        with self.lock:
            self.tasks.extend(tasks)
        self._safe_after(0, lambda: self._refresh_queue())
        self._save_queue()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_requested = False
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
        self._safe_after(0, lambda: self._set_status("▶ 队列处理中…", "warning"))

    # ------------------------------------------------------------------
    # 工作循环
    # ------------------------------------------------------------------
    def _worker_loop(self) -> None:
        while not self._stop_requested:
            task = self._get_next_pending()
            if task is None:
                break
            while self._count_running() >= self.max_concurrent and not self._stop_requested:
                time.sleep(0.1)
            if self._stop_requested:
                break
            self._launch_task(task)
        while self._count_running() > 0:
            time.sleep(0.2)
        self._running = False
        self._safe_after(0, lambda: self._set_status("✅ 队列处理完成", "success"))
        self._save_queue()

    def _get_next_pending(self) -> Optional[QueueTask]:
        with self.lock:
            for t in self.tasks:
                if t.status == "pending":
                    return t
            return None

    def _count_running(self) -> int:
        with self.lock:
            return sum(1 for t in self.tasks if t.status == "running")

    def _launch_task(self, task: QueueTask) -> None:
        task.status = "running"
        task.cancel_event.clear()
        task.thread = threading.Thread(target=self._run_task, args=(task,), daemon=True)
        task.thread.start()
        self._safe_after(0, lambda: self._refresh_queue())

    def _run_task(self, task: QueueTask) -> None:
        try:
            if task.mode == "encode":
                result = Base64Engine.encode_file(
                    task.input_path, task.output_path,
                    progress_cb=lambda c, t, p: self._update_progress(task, p),
                    cancel_event=task.cancel_event,
                    line_length=task.options.get("line_length", 76)
                )
            else:
                if task.options.get("is_text"):
                    result = Base64Engine.decode_text(task.input_path, task.output_path)
                else:
                    result = Base64Engine.decode_file(
                        task.input_path, task.output_path,
                        progress_cb=lambda c, t, p: self._update_progress(task, p),
                        cancel_event=task.cancel_event
                    )
            task.result = result
            task.status = "completed"
            logger.info(f"任务完成: {task.tid}")
        except InterruptedError:
            task.status = "cancelled"
            logger.info(f"任务取消: {task.tid}")
        except Exception as e:
            task.error = str(e)
            task.status = "failed"
            logger.error(f"任务失败: {task.tid} - {e}")
        finally:
            self._safe_after(0, lambda: self._refresh_queue())
            self._save_queue()

    def _update_progress(self, task: QueueTask, pct: float) -> None:
        task.progress = pct
        self._safe_after(0, lambda: self._update_task_progress(task.tid, pct))

    # ------------------------------------------------------------------
    # 任务管理
    # ------------------------------------------------------------------
    def cancel_task(self, tid: str) -> None:
        with self.lock:
            for t in self.tasks:
                if t.tid == tid:
                    if t.status == "pending":
                        t.status = "cancelled"
                        self._safe_after(0, lambda: self._refresh_queue())
                    elif t.status == "running":
                        t.cancel_event.set()
                    break
        self._save_queue()

    def cancel_all(self) -> None:
        self._stop_requested = True
        with self.lock:
            for t in self.tasks:
                if t.status == "pending":
                    t.status = "cancelled"
                elif t.status == "running":
                    t.cancel_event.set()
        self._safe_after(0, lambda: self._refresh_queue())
        self._save_queue()

    def remove_completed(self) -> None:
        with self.lock:
            self.tasks = [t for t in self.tasks if t.status not in ("completed", "cancelled")]
        self._safe_after(0, lambda: self._refresh_queue())
        self._save_queue()

    def clear_all(self) -> None:
        self.cancel_all()
        with self.lock:
            self.tasks.clear()
        self._safe_after(0, lambda: self._refresh_queue())
        self._save_queue()

    def retry_task(self, tid: str) -> None:
        with self.lock:
            for t in self.tasks:
                if t.tid == tid and t.status == "failed":
                    t.status = "pending"
                    t.progress = 0.0
                    t.error = ""
                    t.result = None
                    t.cancel_event = threading.Event()
                    self._safe_after(0, lambda: self._refresh_queue())
                    if not self._running:
                        self.start()
                    break
        self._save_queue()

    # ------------------------------------------------------------------
    # 持久化
    # ------------------------------------------------------------------
    def _save_queue(self) -> None:
        try:
            with self.lock:
                saveable = []
                for t in self.tasks:
                    if t.status in ("pending", "running"):
                        d = t.to_dict()
                        d["status"] = "pending"
                        d["progress"] = 0.0
                        saveable.append(d)
            with open(_QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(saveable, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"保存队列失败: {e}")

    def _load_queue(self) -> None:
        try:
            if not os.path.exists(_QUEUE_FILE):
                return
            with open(_QUEUE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            for d in data:
                try:
                    self.tasks.append(QueueTask.from_dict(d))
                except Exception:
                    continue
            if self.tasks:
                logger.info(f"已加载 {len(self.tasks)} 个未完成任务")
        except Exception as e:
            logger.debug(f"加载队列失败: {e}")

    # ------------------------------------------------------------------
    # 代理方法（桥接到 app 的 UI 线程）
    # ------------------------------------------------------------------
    def _safe_after(self, ms, func):
        try:
            return self.app._safe_after(ms, func)
        except AttributeError:
            pass

    def _refresh_queue(self):
        try:
            self.app.refresh_queue()
        except AttributeError:
            pass

    def _update_task_progress(self, tid, pct):
        try:
            self.app._update_task_progress(tid, pct)
        except AttributeError:
            pass

    def _set_status(self, text, color):
        try:
            self.app._set_status(text, color)
        except AttributeError:
            pass