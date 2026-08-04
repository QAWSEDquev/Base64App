#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Base64 转换引擎 — 纯业务层
文件 ⇄ Base64 编码/解码 · 流式处理 · 原子写入 · 进度回调 · 取消支持
"""
import base64
import hashlib
import logging
import os
import re
import tempfile

logger = logging.getLogger(__name__)

# 可选依赖：chardet 编码检测
try:
    import chardet
    HAS_CHARDET = True
except ImportError:
    HAS_CHARDET = False


class Base64Engine:
    """Base64 编解码引擎，纯业务逻辑，不依赖任何 GUI 框架"""

    CHUNK_ENCODE = 57 * 1024       # 编码读取块大小（57KB → 76字符行）
    CHUNK_DECODE = 4096            # 解码块大小
    BIG_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB 以上强制二进制模式

    @staticmethod
    def _check_same_path(a, b):
        """检查输入输出路径是否相同，防止覆盖"""
        if os.path.abspath(a) == os.path.abspath(b):
            raise ValueError("输入和输出路径不能相同")

    # ------------------------------------------------------------------
    # 编码
    # ------------------------------------------------------------------
    @classmethod
    def encode_file(cls, src, dst, progress_cb=None, cancel_event=None, line_length=76):
        """将文件编码为 Base64 文本文件

        Args:
            src: 源文件路径
            dst: 输出 .b64 文件路径
            progress_cb: 进度回调 (processed, total, percent)
            cancel_event: threading.Event，设置后取消操作
            line_length: 每行字符数，0=不换行
        Returns:
            dict: {size_in, size_out, sha256_in}
        """
        cls._check_same_path(src, dst)
        total_size = os.path.getsize(src)
        if total_size == 0:
            open(dst, "w", encoding="ascii").close()
            if progress_cb:
                progress_cb(0, 0, 100.0)
            return {"size_in": 0, "size_out": 0, "sha256_in": hashlib.sha256(b"").hexdigest()}

        dst_dir = os.path.dirname(os.path.abspath(dst)) or "."
        fd, temp_path = tempfile.mkstemp(dir=dst_dir, suffix=".tmp")
        os.close(fd)

        try:
            with open(src, "rb") as fin, open(temp_path, "w", encoding="ascii") as fout:
                processed = 0
                last_report = 0.0
                buf = []
                while True:
                    if cancel_event and cancel_event.is_set():
                        raise InterruptedError("用户取消操作")
                    chunk = fin.read(cls.CHUNK_ENCODE)
                    if not chunk:
                        break
                    encoded = base64.b64encode(chunk).decode("ascii")
                    if line_length > 0:
                        for i in range(0, len(encoded), line_length):
                            buf.append(encoded[i:i + line_length])
                            if len(buf) >= 100:
                                fout.write("\n".join(buf) + "\n")
                                buf.clear()
                    else:
                        buf.append(encoded)
                        if len(buf) >= 100:
                            fout.write("".join(buf))
                            buf.clear()
                    processed += len(chunk)
                    pct = (processed / total_size) * 100.0
                    if progress_cb and (pct - last_report >= 1.0 or pct >= 100.0):
                        progress_cb(processed, total_size, pct)
                        last_report = pct
                if buf:
                    if line_length > 0:
                        fout.write("\n".join(buf) + "\n")
                    else:
                        fout.write("".join(buf))

            # 计算源文件 SHA256
            sha = hashlib.sha256()
            with open(src, "rb") as f:
                while True:
                    d = f.read(65536)
                    if not d:
                        break
                    sha.update(d)
            os.replace(temp_path, dst)
            return {"size_in": total_size, "size_out": os.path.getsize(dst),
                    "sha256_in": sha.hexdigest()}
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    # ------------------------------------------------------------------
    # 解码
    # ------------------------------------------------------------------
    @classmethod
    def decode_file(cls, src, dst, progress_cb=None, cancel_event=None):
        """将 Base64 文件还原为原始文件

        自动选择解码策略：
        - 小文件 + chardet 可用 → 文本模式（编码检测，兼容性好）
        - 大文件或无 chardet → 二进制模式（快速，直接过滤非 Base64 字符）
        """
        cls._check_same_path(src, dst)
        file_size = os.path.getsize(src)
        if file_size > cls.BIG_FILE_THRESHOLD or not HAS_CHARDET:
            return cls._decode_file_binary(src, dst, progress_cb, cancel_event)
        return cls._decode_file_text(src, dst, progress_cb, cancel_event)

    @classmethod
    def _decode_file_text(cls, src, dst, progress_cb, cancel_event):
        """文本模式解码 — 逐行读取，自动检测编码"""
        encoding = "utf-8"
        if HAS_CHARDET:
            with open(src, "rb") as f:
                raw_sample = f.read(min(cls.CHUNK_ENCODE, os.path.getsize(src)))
            detected = chardet.detect(raw_sample)
            if detected and detected.get("encoding"):
                encoding = detected["encoding"]

        dst_dir = os.path.dirname(os.path.abspath(dst)) or "."
        fd, temp_path = tempfile.mkstemp(dir=dst_dir, suffix=".tmp")
        os.close(fd)
        try:
            total_size = os.path.getsize(src)
            processed = 0
            last_report = 0.0
            decoded_any = False
            b64_buf = []
            buf_len = 0
            with open(src, "r", encoding=encoding, errors="ignore") as fin, \
                 open(temp_path, "wb") as fout:
                for line in fin:
                    if cancel_event and cancel_event.is_set():
                        raise InterruptedError("用户取消操作")
                    clean = re.sub(r'[^A-Za-z0-9+/=]', '', line)
                    if clean:
                        b64_buf.append(clean)
                        buf_len += len(clean)
                        while buf_len >= cls.CHUNK_DECODE * 4:
                            data = "".join(b64_buf)
                            usable = (len(data) // 4) * 4
                            if usable == 0:
                                break
                            chunk = data[:usable]
                            remainder = data[usable:]
                            fout.write(base64.b64decode(chunk, validate=True))
                            b64_buf = [remainder] if remainder else []
                            buf_len = len(remainder)
                            decoded_any = True
                    processed += len(line.encode(encoding, errors="ignore"))
                    pct = (processed / total_size) * 100.0 if total_size else 100.0
                    if progress_cb and (pct - last_report >= 1.0 or pct >= 100.0):
                        progress_cb(processed, total_size, pct)
                        last_report = pct
                if b64_buf:
                    tail = "".join(b64_buf)
                    if tail.strip("="):
                        pad = (4 - len(tail) % 4) % 4
                        if pad:
                            tail += "=" * pad
                        fout.write(base64.b64decode(tail, validate=True))
                        decoded_any = True
                if not decoded_any:
                    raise ValueError("文件中未找到有效的 Base64 数据")
            if progress_cb:
                progress_cb(total_size, total_size, 100.0)
            os.replace(temp_path, dst)
            return {"size_out": os.path.getsize(dst)}
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    @classmethod
    def _decode_file_binary(cls, src, dst, progress_cb, cancel_event):
        """二进制模式解码 — 快速过滤非 Base64 字符"""
        dst_dir = os.path.dirname(os.path.abspath(dst)) or "."
        fd, temp_path = tempfile.mkstemp(dir=dst_dir, suffix=".tmp")
        os.close(fd)
        try:
            total_size = os.path.getsize(src)
            processed = 0
            last_report = 0.0
            decoded_any = False
            b64_buf = []
            buf_len = 0
            with open(src, "rb") as fin, open(temp_path, "wb") as fout:
                while True:
                    if cancel_event and cancel_event.is_set():
                        raise InterruptedError("用户取消操作")
                    chunk = fin.read(65536)
                    if not chunk:
                        break
                    clean = re.sub(rb'[^A-Za-z0-9+/=]', b'', chunk).decode("ascii")
                    if clean:
                        b64_buf.append(clean)
                        buf_len += len(clean)
                        while buf_len >= cls.CHUNK_DECODE * 4:
                            data = "".join(b64_buf)
                            usable = (len(data) // 4) * 4
                            if usable == 0:
                                break
                            chunk_txt = data[:usable]
                            remainder = data[usable:]
                            fout.write(base64.b64decode(chunk_txt, validate=True))
                            b64_buf = [remainder] if remainder else []
                            buf_len = len(remainder)
                            decoded_any = True
                    processed += len(chunk)
                    pct = (processed / total_size) * 100.0 if total_size else 100.0
                    if progress_cb and (pct - last_report >= 1.0 or pct >= 100.0):
                        progress_cb(processed, total_size, pct)
                        last_report = pct
                if b64_buf:
                    tail = "".join(b64_buf)
                    if tail.strip("="):
                        pad = (4 - len(tail) % 4) % 4
                        if pad:
                            tail += "=" * pad
                        fout.write(base64.b64decode(tail, validate=True))
                        decoded_any = True
                if not decoded_any:
                    raise ValueError("文件中未找到有效的 Base64 数据")
            if progress_cb:
                progress_cb(total_size, total_size, 100.0)
            os.replace(temp_path, dst)
            return {"size_out": os.path.getsize(dst)}
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise

    # ------------------------------------------------------------------
    # 文本解码
    # ------------------------------------------------------------------
    @classmethod
    def decode_text(cls, text, dst):
        """将 Base64 文本字符串直接解码为文件（不依赖文件路径）"""
        clean = re.sub(r'[^A-Za-z0-9+/=]', '', text)
        if not clean:
            raise ValueError("输入内容中未找到有效的 Base64 数据")
        pad = (4 - len(clean) % 4) % 4
        if pad:
            clean += "=" * pad
        dst_dir = os.path.dirname(os.path.abspath(dst)) or "."
        fd, temp_path = tempfile.mkstemp(dir=dst_dir, suffix=".tmp")
        os.close(fd)
        try:
            with open(temp_path, "wb") as fout:
                for i in range(0, len(clean), cls.CHUNK_DECODE):
                    chunk = clean[i:i + cls.CHUNK_DECODE]
                    fout.write(base64.b64decode(chunk, validate=True))
            os.replace(temp_path, dst)
            return {"size_out": os.path.getsize(dst)}
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise