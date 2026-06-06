"""剪贴板工具单元测试。"""

from unittest.mock import MagicMock, patch

from ohmycode.cli.clipboard import copy_to_system_clipboard


class TestCopyToSystemClipboard:
    """copy_to_system_clipboard 跨平台测试。"""

    def test_macos_pbcopy_success(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Darwin"
            mock_run.return_value = MagicMock(returncode=0)

            assert copy_to_system_clipboard("hello") is True
            mock_run.assert_called_once_with(
                ["pbcopy"], input="hello", text=True, timeout=5,
            )

    def test_macos_pbcopy_not_found(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Darwin"
            mock_run.side_effect = FileNotFoundError()

            assert copy_to_system_clipboard("hello") is False

    def test_macos_pbcopy_timeout(self):
        import subprocess

        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Darwin"
            mock_run.side_effect = subprocess.TimeoutExpired("pbcopy", 5)

            assert copy_to_system_clipboard("hello") is False

    def test_linux_wl_copy_success(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.shutil.which") as mock_which,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Linux"
            mock_which.side_effect = lambda cmd: {
                "wl-copy": "/usr/bin/wl-copy",
            }.get(cmd)
            mock_run.return_value = MagicMock(returncode=0)

            assert copy_to_system_clipboard("hello") is True
            mock_run.assert_called_once_with(
                ["wl-copy"], input="hello", text=True, timeout=5,
            )

    def test_linux_fallback_to_xclip(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.shutil.which") as mock_which,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Linux"
            mock_which.side_effect = lambda cmd: {
                "wl-copy": None,
                "xclip": "/usr/bin/xclip",
            }.get(cmd)

            def run_side_effect(cmd, **kwargs):
                if cmd[0] == "wl-copy":
                    raise FileNotFoundError()
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            assert copy_to_system_clipboard("hello") is True

    def test_linux_fallback_to_xsel(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.shutil.which") as mock_which,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Linux"
            mock_which.side_effect = lambda cmd: {
                "wl-copy": None,
                "xclip": None,
                "xsel": "/usr/bin/xsel",
            }.get(cmd)
            mock_run.return_value = MagicMock(returncode=0)

            assert copy_to_system_clipboard("hello") is True
            mock_run.assert_called_with(
                ["xsel", "--clipboard", "--input"],
                input="hello", text=True, timeout=5,
            )

    def test_linux_no_tools_available(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.shutil.which") as mock_which,
        ):
            mock_platform.system.return_value = "Linux"
            mock_which.return_value = None

            assert copy_to_system_clipboard("hello") is False

    def test_windows_clip_success(self):
        with (
            patch("ohmycode.cli.clipboard.platform") as mock_platform,
            patch("ohmycode.cli.clipboard.subprocess.run") as mock_run,
        ):
            mock_platform.system.return_value = "Windows"
            mock_run.return_value = MagicMock(returncode=0)

            assert copy_to_system_clipboard("hello") is True
            mock_run.assert_called_once_with(
                ["clip"], input="hello", text=True, timeout=5,
            )

    def test_unknown_platform_returns_false(self):
        with patch("ohmycode.cli.clipboard.platform") as mock_platform:
            mock_platform.system.return_value = "FreeBSD"

            assert copy_to_system_clipboard("hello") is False
