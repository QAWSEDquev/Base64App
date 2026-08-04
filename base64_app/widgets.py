#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KivyMD 文件选择器 — 手机触屏适配
全屏模态 · 大按钮触控 · 路径显示 · 目录/文件选择
"""
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.modalview import ModalView

from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel


class FilePicker(ModalView):
    """手机触屏版文件选择器 — 全屏模态，适配手指操作"""

    def __init__(self, callback, title="选择文件", dir_select=False, **kwargs):
        """
        Args:
            callback: 回调函数，接收选中路径 (path: str)
            title: 标题
            dir_select: True=选择目录, False=选择文件
        """
        super().__init__(size_hint=(0.94, 0.94), **kwargs)
        self.callback = callback
        self.dir_select = dir_select
        self.selected = None

        box = BoxLayout(orientation="vertical", spacing=dp(8), padding=dp(8))

        # ---- 标题栏 ----
        title_bar = BoxLayout(size_hint_y=None, height=dp(56))
        title_bar.add_widget(MDLabel(
            text=title, font_style="H6", halign="left"
        ))
        close_btn = MDIconButton(
            icon="close", on_release=lambda *a: self.dismiss(),
            theme_icon_color="Custom", icon_color="grey"
        )
        title_bar.add_widget(close_btn)
        box.add_widget(title_bar)

        # ---- 当前路径显示 ----
        self.path_label = MDLabel(
            text="", size_hint_y=None, height=dp(40),
            theme_text_color="Secondary", font_style="Caption"
        )
        box.add_widget(self.path_label)

        # ---- 文件列表 ----
        self.chooser = FileChooserListView(
            dirselect=self.dir_select,
            filters=[] if self.dir_select else None,
            size_hint_y=1.0
        )
        self.chooser.bind(on_selection=self._on_sel, on_submit=self._on_submit)
        box.add_widget(self.chooser, 1)

        # ---- 确定按钮 ----
        ok_btn = MDRaisedButton(
            text="确定", size_hint=(0.7, None), height=dp(52),
            pos_hint={"center_x": 0.5},
            on_release=lambda *a: self._confirm()
        )
        box.add_widget(ok_btn)

        self.add_widget(box)

    def _on_sel(self, chooser, sel):
        if sel:
            self.selected = sel[0]
            self.path_label.text = sel[0]

    def _on_submit(self, chooser, sel, touch):
        if sel:
            self.selected = sel[0]
            self.path_label.text = sel[0]

    def _confirm(self):
        if getattr(self, "selected", None):
            cb = self.callback
            self.dismiss()
            # 延迟回调，确保 dismiss 完成
            Clock.schedule_once(lambda dt: cb(self.selected), 0.1)