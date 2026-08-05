#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主界面 — 编码/解码操作面板
KivyMD 手机触屏版 · 纯 Python 构建 · 暗色主题 · Material Design 3
"""
import logging
import os

from kivy.metrics import dp
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView

from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.card import MDCard
from kivymd.uix.toolbar import MDTopAppBar
from kivymd.uix.selectioncontrol import MDCheckbox

from .widgets import FilePicker

logger = logging.getLogger(__name__)


class MainScreen(Screen):
    """主操作界面 — 编码卡片 + 解码卡片 + 存储权限提示"""

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
            title="Base64 转换工具",
            elevation=2,
            right_action_items=[
                ["playlist-check", lambda *a: self._go_to_queue()]
            ]
        )
        layout.add_widget(self.toolbar)

        # ---- 可滚动内容 ----
        scroll = ScrollView()
        content = BoxLayout(
            orientation="vertical", padding=dp(12),
            spacing=dp(12), size_hint_y=None
        )
        content.bind(minimum_height=content.setter("height"))

        self._build_storage_warning(content)
        self._build_encode_card(content)
        self._build_decode_card(content)

        scroll.add_widget(content)
        layout.add_widget(scroll)
        self.add_widget(layout)

    def _go_to_queue(self):
        if self.manager:
            self.manager.current = "queue"

    # ------------------------------------------------------------------
    # 存储权限提示栏
    # ------------------------------------------------------------------
    def _build_storage_warning(self, parent):
        """在界面顶部显示存储权限提示"""
        warn_card = MDCard(
            padding=dp(8), size_hint_y=None, adaptive_height=True,
            md_bg_color=[0.1, 0.1, 0.15, 1]
        )
        warn_layout = BoxLayout(orientation="horizontal", spacing=dp(8))
        warn_layout.add_widget(MDLabel(
            text="💾", size_hint_x=None, width=dp(30),
            halign="center", valign="middle"
        ))
        warn_layout.add_widget(MDLabel(
            text="如需访问手机存储，请在系统设置中授予「文件和媒体」权限",
            font_style="Caption", theme_text_color="Secondary",
            size_hint_x=1.0, halign="left"
        ))
        warn_card.add_widget(warn_layout)
        parent.add_widget(warn_card)

    # ------------------------------------------------------------------
    # 编码卡片
    # ------------------------------------------------------------------
    def _build_encode_card(self, parent):
        enc = MDCard(padding=dp(16), size_hint_y=None, adaptive_height=True)
        enc_layout = BoxLayout(orientation="vertical", spacing=dp(12))
        enc.add_widget(enc_layout)

        # 标题行
        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40))
        title_row.add_widget(MDLabel(
            text="📁 文件 → Base64", font_style="H6", size_hint_x=1.0
        ))
        enc_layout.add_widget(title_row)

        # 批量模式开关
        batch_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.enc_batch = MDCheckbox(active=False, size_hint_x=None, width=dp(40))
        batch_row.add_widget(self.enc_batch)
        batch_row.add_widget(MDLabel(
            text="批量模式（加入队列）", size_hint_x=1.0,
            theme_text_color="Secondary", font_style="Body2"
        ))
        enc_layout.add_widget(batch_row)

        # 分隔线
        enc_layout.add_widget(self._divider())

        # 输入文件
        enc_layout.add_widget(MDLabel(
            text="选择源文件", theme_text_color="Secondary",
            size_hint_y=None, height=dp(18), font_style="Caption"
        ))
        input_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        self.enc_input = MDTextField(
            hint_text="点击右侧按钮选择...",
            readonly=True, multiline=False,
            size_hint_x=1.0, size_hint_y=None, height=dp(48)
        )
        input_row.add_widget(self.enc_input)
        input_row.add_widget(MDRaisedButton(
            text="📂", size_hint_x=None, width=dp(56),
            on_release=lambda *a: self._pick_file("enc_input")
        ))
        enc_layout.add_widget(input_row)

        # 输出路径
        enc_layout.add_widget(MDLabel(
            text="输出路径（.b64 文件）", theme_text_color="Secondary",
            size_hint_y=None, height=dp(18), font_style="Caption"
        ))
        output_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        self.enc_output = MDTextField(
            text="", hint_text="自动生成",
            readonly=True, multiline=False,
            size_hint_x=1.0, size_hint_y=None, height=dp(48)
        )
        output_row.add_widget(self.enc_output)
        output_row.add_widget(MDRaisedButton(
            text="📁", size_hint_x=None, width=dp(56),
            on_release=lambda *a: self._pick_dir("enc_output")
        ))
        enc_layout.add_widget(output_row)

        # 换行选项
        wrap_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.enc_wrap = MDCheckbox(active=True, size_hint_x=None, width=dp(40))
        wrap_row.add_widget(self.enc_wrap)
        wrap_row.add_widget(MDLabel(
            text="每76字符换行（标准 Base64）", size_hint_x=1.0,
            theme_text_color="Secondary", font_style="Body2"
        ))
        enc_layout.add_widget(wrap_row)

        # 开始按钮 — 注意：不在 build 时调用 _get_app，用默认颜色
        enc_layout.add_widget(MDRaisedButton(
            text="🚀 开始编码",
            on_release=lambda *a: self._do_encode(),
            size_hint_y=None, height=dp(56)
        ))

        parent.add_widget(enc)

    # ------------------------------------------------------------------
    # 解码卡片
    # ------------------------------------------------------------------
    def _build_decode_card(self, parent):
        dec = MDCard(padding=dp(16), size_hint_y=None, adaptive_height=True)
        dec_layout = BoxLayout(orientation="vertical", spacing=dp(12))
        dec.add_widget(dec_layout)

        # 标题行
        title_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(40))
        title_row.add_widget(MDLabel(
            text="🔓 Base64 → 文件", font_style="H6", size_hint_x=1.0
        ))
        dec_layout.add_widget(title_row)

        # 批量模式开关
        batch_row = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
        self.dec_batch = MDCheckbox(active=True, size_hint_x=None, width=dp(40))
        batch_row.add_widget(self.dec_batch)
        batch_row.add_widget(MDLabel(
            text="批量模式（加入队列）", size_hint_x=1.0,
            theme_text_color="Secondary", font_style="Body2"
        ))
        dec_layout.add_widget(batch_row)

        # 分隔线
        dec_layout.add_widget(self._divider())

        # 输入文件
        dec_layout.add_widget(MDLabel(
            text="选择 .b64 文件", theme_text_color="Secondary",
            size_hint_y=None, height=dp(18), font_style="Caption"
        ))
        input_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        self.dec_input = MDTextField(
            text="", hint_text="点击右侧按钮选择...",
            readonly=True, multiline=False,
            size_hint_x=1.0, size_hint_y=None, height=dp(48)
        )
        input_row.add_widget(self.dec_input)
        input_row.add_widget(MDRaisedButton(
            text="📂", size_hint_x=None, width=dp(56),
            on_release=lambda *a: self._pick_file("dec_input")
        ))
        dec_layout.add_widget(input_row)

        # 输出路径
        dec_layout.add_widget(MDLabel(
            text="输出路径（还原的文件）", theme_text_color="Secondary",
            size_hint_y=None, height=dp(18), font_style="Caption"
        ))
        output_row = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(50), spacing=dp(8))
        self.dec_output = MDTextField(
            text="", hint_text="自动生成",
            readonly=True, multiline=False,
            size_hint_x=1.0, size_hint_y=None, height=dp(48)
        )
        output_row.add_widget(self.dec_output)
        output_row.add_widget(MDRaisedButton(
            text="📁", size_hint_x=None, width=dp(56),
            on_release=lambda *a: self._pick_dir("dec_output")
        ))
        dec_layout.add_widget(output_row)

        # 开始按钮
        dec_layout.add_widget(MDRaisedButton(
            text="🔓 开始解码",
            on_release=lambda *a: self._do_decode(),
            size_hint_y=None, height=dp(56)
        ))

        parent.add_widget(dec)

    # ------------------------------------------------------------------
    # 辅助 UI
    # ------------------------------------------------------------------
    @staticmethod
    def _divider():
        """视觉分隔线"""
        from kivy.uix.widget import Widget
        return Widget(size_hint_y=None, height=dp(1),
                      canvas_before=[{
                          'Color': (0.2, 0.2, 0.25, 1),
                          'Rectangle': (0, 0, 10000, 1)
                      }])

    # ------------------------------------------------------------------
    # 文件选择
    # ------------------------------------------------------------------
    def _pick_file(self, target):
        """选择文件并自动填入路径，自动生成输出路径"""
        def wrapped_cb(path):
            if path:
                field = getattr(self, target)
                field.text = path
                # 自动生成输出路径
                if target == "enc_input":
                    self.enc_output.text = path + ".b64"
                elif target == "dec_input":
                    base = path[:-4] if path.endswith(".b64") else path + ".decoded"
                    self.dec_output.text = base
        FilePicker(callback=wrapped_cb, title="选择文件").open()

    def _pick_dir(self, target):
        """选择目录（自动附加文件名到选择的目录路径）"""
        def wrapped_cb(path):
            if path:
                field = getattr(self, target)
                # 如果已有文件名，保留它；否则自动生成
                current = field.text.strip()
                if current and '/' in current:
                    old_name = current.rsplit('/', 1)[-1]
                    field.text = path.rstrip('/') + '/' + old_name
                else:
                    field.text = path
        FilePicker(callback=wrapped_cb, title="选择目录", dir_select=True).open()

    # ------------------------------------------------------------------
    # 操作执行
    # ------------------------------------------------------------------
    def _do_encode(self):
        """执行编码操作"""
        app = self._get_app()
        if not app:
            return

        src = self.enc_input.text.strip()
        dst = self.enc_output.text.strip()
        if not src or not os.path.isfile(src):
            app.snack("⚠️ 请选择有效的输入文件")
            return
        if not dst:
            app.snack("⚠️ 请指定输出路径")
            return

        line_len = 76 if self.enc_wrap.active else 0
        if self.enc_batch.active:
            app.add_task("encode", src, dst, {"line_length": line_len})
            app.snack("➕ 已添加到队列")
        else:
            app.start_single("encode", src, dst, line_len=line_len)

    def _do_decode(self):
        """执行解码操作"""
        app = self._get_app()
        if not app:
            return

        src = self.dec_input.text.strip()
        dst = self.dec_output.text.strip()
        if not src:
            app.snack("⚠️ 请选择输入文件")
            return
        if not dst:
            app.snack("⚠️ 请指定输出路径")
            return

        if self.dec_batch.active:
            app.add_task("decode", src, dst, {"is_text": False})
            app.snack("➕ 已添加到队列")
        else:
            app.start_single("decode", src, dst)

    @staticmethod
    def _get_app():
        """安全获取 App 实例"""
        from kivymd.app import MDApp
        app = MDApp.get_running_app()
        if app is None:
            logger.error("无法获取 App 实例")
        return app