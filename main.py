#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base64 转换工具 — 手机版 (KivyMD)
模块化重构 · 适配触屏 · 暗色主题 · 批量队列 · 任务持久化

模块结构:
  base64_app/
    ├── __init__.py      — 包声明
    ├── engine.py        — Base64 编解码引擎（纯业务）
    ├── models.py        — 任务模型 + 批量执行器 + 持久化
    ├── widgets.py       — 文件选择器等通用组件
    ├── screens.py       — 主界面（编码/解码卡片）
    └── queue_screen.py  — 任务队列界面
  main.py                — 应用入口
  buildozer.spec         — Buildozer 构建配置
"""
import logging
import os
import threading

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager
from kivymd.app import MDApp
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.list import ThreeLineListItem

from base64_app.engine import Base64Engine
from base64_app.models import BatchExecutor, QueueTask
from base64_app.screens import MainScreen
from base64_app.queue_screen import QueueScreen

# ---- 日志配置 ----
_APP_DIR = os.path.join(os.path.expanduser("~"), ".base64_converter")
try:
    os.makedirs(_APP_DIR, exist_ok=True)
except Exception:
    pass

logging.basicConfig(
    filename=os.path.join(_APP_DIR, "base64_converter.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s %(message)s"
)
logger = logging.getLogger(__name__)


class Base64App(MDApp):
    """Base64 转换工具主应用 — KivyMD 手机版"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        self.theme_cls.material_style = "M3"

        self.executor = BatchExecutor(self, max_concurrent=2)
        self._counter = 0
        self.main = None
        self.queue = None

    def build(self):
        """构建应用 UI"""
        Window.sync_platform_ = True
        Window.title = "Base64 转换工具"

        self.sm = ScreenManager()
        self.main = MainScreen(name="main")
        self.queue = QueueScreen(name="queue")
        self.sm.add_widget(self.main)
        self.sm.add_widget(self.queue)

        # 启动后检查存储权限
        Clock.schedule_once(lambda dt: self._check_storage_permission(), 1)

        return self.sm

    # ------------------------------------------------------------------
    # 存储权限处理
    # ------------------------------------------------------------------
    def _check_storage_permission(self):
        """检查 Android 存储权限"""
        try:
            from android.permissions import request_permissions, Permission, check_permission
            perms = [
                Permission.READ_EXTERNAL_STORAGE,
                Permission.WRITE_EXTERNAL_STORAGE,
            ]
            all_granted = all(check_permission(p) for p in perms)
            if not all_granted:
                def callback(permissions, grant_results):
                    if all(grant_results):
                        self.snack("✅ 存储权限已获取")
                    else:
                        self.snack("⚠️ 部分权限未授予，可在系统设置中手动开启")
                request_permissions(perms, callback)
            else:
                logger.info("存储权限已授予")
        except ImportError:
            logger.debug("非 Android 环境，跳过权限请求")
        except Exception as e:
            logger.warning(f"权限请求失败: {e}")

    # ------------------------------------------------------------------
    # 线程安全 UI 调度
    # ------------------------------------------------------------------
    def _safe_after(self, ms, func):
        """安全地在 UI 线程调度函数（供 BatchExecutor 调用）"""
        try:
            return Clock.schedule_once(lambda dt: func(), ms / 1000.0)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Snackbar 通知
    # ------------------------------------------------------------------
    def snack(self, text, duration=2):
        """显示 Snackbar 通知"""
        try:
            Snackbar(text=text, duration=duration).open()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 单任务模式
    # ------------------------------------------------------------------
    def start_single(self, mode, src, dst, line_len=76):
        """在后台线程中执行单个任务"""
        self.snack("⏳ 处理中...")

        def work():
            try:
                if mode == "encode":
                    r = Base64Engine.encode_file(src, dst, line_length=line_len)
                    size = r["size_in"] / 1024
                    unit = "KB"
                    if r["size_in"] > 1024 * 1024:
                        size = r["size_in"] / (1024 * 1024)
                        unit = "MB"
                    Clock.schedule_once(
                        lambda dt: self.snack(f"✅ 编码完成 {size:.1f}{unit}")
                    )
                else:
                    r = Base64Engine.decode_file(src, dst)
                    size = r["size_out"] / 1024
                    unit = "KB"
                    if r["size_out"] > 1024 * 1024:
                        size = r["size_out"] / (1024 * 1024)
                        unit = "MB"
                    Clock.schedule_once(
                        lambda dt: self.snack(f"✅ 解码完成 {size:.1f}{unit}")
                    )
            except Exception as e:
                Clock.schedule_once(
                    lambda dt: self.snack(f"❌ {str(e)[:50]}")
                )

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------------
    # 批量任务
    # ------------------------------------------------------------------
    def add_task(self, mode, src, dst, options=None):
        """添加任务到队列"""
        self._counter += 1
        t = QueueTask(
            tid=str(self._counter),
            mode=mode,
            input_path=src,
            output_path=dst,
            options=options or {}
        )
        self.executor.add_task(t)
        self.snack("已加入队列")

    def start_q(self):
        """启动队列执行"""
        self.executor.start()
        self.snack("▶ 队列开始")

    def cancel_q(self):
        """取消所有队列任务"""
        self.executor.cancel_all()
        self.refresh_queue()

    def remove_q(self):
        """移除已完成的任务"""
        self.executor.remove_completed()

    def clear_q(self):
        """清空所有任务"""
        self.executor.clear_all()

    def retry_q(self, tid):
        """重试失败的任务"""
        self.executor.retry_task(tid)

    # ------------------------------------------------------------------
    # 队列刷新
    # ------------------------------------------------------------------
    def refresh_queue(self):
        """刷新队列界面的任务列表"""
        if not self.queue:
            return
        q = self.queue
        q.list.clear_widgets()

        with self.executor.lock:
            tasks = list(self.executor.tasks)

        icons = {
            "pending": "⏳", "running": "🔄", "completed": "✅",
            "failed": "❌", "cancelled": "⏹"
        }
        done = {"pending": 0, "running": 0, "completed": 0,
                "failed": 0, "cancelled": 0}

        for t in tasks:
            done[t.status] = done.get(t.status, 0) + 1
            icon = icons.get(t.status, "❓")
            txt = f"{icon} [{t.tid}] {t.mode.upper()} {os.path.basename(t.input_path)}"
            sub = f"状态:{t.status} 进度:{t.progress:.0f}%"
            if t.error:
                sub += f" | 错误:{t.error[:30]}"
            item = ThreeLineListItem(
                text=txt,
                secondary_text=sub,
                tertiary_text=os.path.basename(t.output_path)
            )
            q.list.add_widget(item)

        q.status_label.text = (
            f"等待:{done['pending']} 运行:{done['running']} "
            f"完成:{done['completed']} 失败:{done['failed']} "
            f"取消:{done['cancelled']}"
        )

    def _update_task_progress(self, tid, pct):
        pass

    def _set_status(self, text, color):
        self.snack(text)

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def on_stop(self):
        """应用关闭时取消所有任务"""
        self.executor.cancel_all()
        logger.info("应用关闭，已取消所有任务")


if __name__ == "__main__":
    Base64App().run()