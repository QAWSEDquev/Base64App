#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
任务队列界面 — 批量任务管理
显示任务列表、进度、状态、操作按钮
优化：手机横屏适配 · 滚动按钮 · 紧凑布局
"""
import logging
import os

from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView

from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.list import MDList

logger = logging.getLogger(__name__)


class QueueScreen(Screen):
    """任务队列管理界面 — 手机触屏优化"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._built = False

    def on_pre_enter(self):
        if not self._built:
            self._built = True
            self._build_ui()

    def _build_ui(self):
        layout = BoxLayout(orientation="vertical")

        # ---- 顶部工具栏 ----
        self.toolbar = MDTopAppBar(
            title="任务队列",
            left_action_items=[["arrow-left", lambda *a: self._go_back()]]
        )
        layout.add_widget(self.toolbar)

        # ---- 状态统计 ----
        self.status_label = MDLabel(
            text="等待:0 运行:0 完成:0 失败:0 取消:0",
            halign="center", size_hint_y=None, height=dp(40),
            font_style="Body2", theme_text_color="Secondary"
        )
        layout.add_widget(self.status_label)

        # ---- 操作按钮（横向滚动，防止窄屏截断） ----
        btn_scroll = ScrollView(
            size_hint_y=None, height=dp(56),
            bar_width=0, do_scroll_y=False
        )
        btns = BoxLayout(
            size_hint_x=None, height=dp(56),
            spacing=dp(6), padding=dp(8)
        )
        btns.bind(minimum_width=btns.setter("width"))

        actions = [
            ("▶ 开始", "start_q"),
            ("⏹ 取消", "cancel_q"),
            ("🗑 清理", "remove_q"),
            ("🧹 清空", "clear_q"),
        ]
        for text, method in actions:
            btn = MDRaisedButton(
                text=text,
                on_release=lambda *a, m=method: self._invoke(m),
                size_hint_x=None, width=dp(90),
                height=dp(44)
            )
            btns.add_widget(btn)

        btn_scroll.add_widget(btns)
        layout.add_widget(btn_scroll)

        # ---- 任务列表 ----
        self.list = MDList()
        scroll = ScrollView()
        scroll.add_widget(self.list)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _go_back(self):
        """返回主界面"""
        if self.manager:
            self.manager.current = "main"

    def _invoke(self, method_name):
        """通过 MDApp 调用方法"""
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        if app and hasattr(app, method_name):
            getattr(app, method_name)()