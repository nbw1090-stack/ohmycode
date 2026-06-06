"""系统剪贴板工具 — 跨平台复制文本到系统剪贴板。

参考 opencode 的实现方式，使用平台原生命令写入系统剪贴板，
同时由调用方配合 Textual 内置的 OSC52 支持，实现最大兼容性。

支持平台：
- macOS: pbcopy
- Linux: wl-copy (Wayland) / xclip / xsel (X11)
- Windows: clip
"""

import platform
import shutil
import subprocess


def _copy_macos(text: str) -> bool:
    """macOS: 使用 pbcopy 写入剪贴板。"""
    try:
        proc = subprocess.run(
            ["pbcopy"],
            input=text,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _copy_linux(text: str) -> bool:
    """Linux: 依次尝试 wl-copy / xclip / xsel。"""
    # Wayland
    if shutil.which("wl-copy"):
        try:
            proc = subprocess.run(
                ["wl-copy"],
                input=text,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # X11 — xclip
    if shutil.which("xclip"):
        try:
            proc = subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # X11 — xsel
    if shutil.which("xsel"):
        try:
            proc = subprocess.run(
                ["xsel", "--clipboard", "--input"],
                input=text,
                text=True,
                timeout=5,
            )
            if proc.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return False


def _copy_windows(text: str) -> bool:
    """Windows: 使用 clip 命令写入剪贴板。"""
    try:
        proc = subprocess.run(
            ["clip"],
            input=text,
            text=True,
            timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def copy_to_system_clipboard(text: str) -> bool:
    """将文本复制到系统剪贴板。

    使用平台原生命令（pbcopy / wl-copy / xclip / xsel / clip）写入。
    调用方还应同时调用 Textual 的 ``App.copy_to_clipboard()`` 以触发
    OSC52 转义序列，覆盖 SSH/远程终端场景。

    Args:
        text: 要复制的文本内容。

    Returns:
        True 表示原生命令成功写入，False 表示无可用工具或执行失败。
    """
    system = platform.system()
    if system == "Darwin":
        return _copy_macos(text)
    elif system == "Linux":
        return _copy_linux(text)
    elif system == "Windows":
        return _copy_windows(text)
    return False
