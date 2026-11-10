"""Copy text to the clipboard the way password managers do.

On Windows the text is tagged so that it is **excluded from clipboard history
(Win+V) and from cloud clipboard sync**, and it is wiped automatically after a
timeout, unless the user has copied something else in the meantime.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import time

DEFAULT_CLEAR_SECONDS = 45


class ClipboardError(RuntimeError):
    pass


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- Windows
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _CF_UNICODETEXT = 13
    _GMEM_MOVEABLE = 0x0002

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.OpenClipboard.argtypes = [wintypes.HWND]
    _user32.OpenClipboard.restype = wintypes.BOOL
    _user32.CloseClipboard.restype = wintypes.BOOL
    _user32.EmptyClipboard.restype = wintypes.BOOL
    _user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    _user32.SetClipboardData.restype = wintypes.HANDLE
    _user32.GetClipboardData.argtypes = [wintypes.UINT]
    _user32.GetClipboardData.restype = wintypes.HANDLE
    _user32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    _user32.RegisterClipboardFormatW.restype = wintypes.UINT
    _kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    _kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    _kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalLock.restype = ctypes.c_void_p
    _kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    _kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]

    def _open() -> None:
        for _ in range(20):
            if _user32.OpenClipboard(None):
                return
            time.sleep(0.05)
        raise ClipboardError("Clipboard is locked by another application")

    def _put(fmt: int, payload: bytes) -> None:
        handle = _kernel32.GlobalAlloc(_GMEM_MOVEABLE, len(payload))
        if not handle:
            raise ClipboardError("GlobalAlloc failed")
        pointer = _kernel32.GlobalLock(handle)
        ctypes.memmove(pointer, payload, len(payload))
        _kernel32.GlobalUnlock(handle)
        if not _user32.SetClipboardData(fmt, handle):
            _kernel32.GlobalFree(handle)
            raise ClipboardError("SetClipboardData failed")

    def _set_private_text(text: str) -> None:
        _open()
        try:
            _user32.EmptyClipboard()
            _put(_CF_UNICODETEXT, (text + "\0").encode("utf-16-le"))
            zero_dword = (0).to_bytes(4, "little")
            for name, payload in (
                ("ExcludeClipboardContentFromMonitorProcessing", b"\0"),
                ("CanIncludeInClipboardHistory", zero_dword),
                ("CanUploadToCloudClipboard", zero_dword),
            ):
                _put(_user32.RegisterClipboardFormatW(name), payload)
        finally:
            _user32.CloseClipboard()

    def _get_text() -> str | None:
        _open()
        try:
            handle = _user32.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                return None
            pointer = _kernel32.GlobalLock(handle)
            try:
                return ctypes.wstring_at(pointer)
            finally:
                _kernel32.GlobalUnlock(handle)
        finally:
            _user32.CloseClipboard()

    def _clear() -> None:
        _open()
        try:
            _user32.EmptyClipboard()
        finally:
            _user32.CloseClipboard()

# --------------------------------------------------------------------------- POSIX
else:

    def _posix_tool(read: bool) -> list[str]:
        if shutil.which("wl-copy") and shutil.which("wl-paste"):
            return ["wl-paste", "--no-newline"] if read else ["wl-copy"]
        if shutil.which("xclip"):
            return ["xclip", "-selection", "clipboard"] + (["-o"] if read else [])
        if shutil.which("pbcopy"):
            return ["pbpaste"] if read else ["pbcopy"]
        raise ClipboardError("No clipboard tool found (install wl-clipboard or xclip)")

    def _set_private_text(text: str) -> None:
        subprocess.run(_posix_tool(read=False), input=text.encode(), check=True)  # noqa: S603

    def _get_text() -> str | None:
        result = subprocess.run(_posix_tool(read=True), capture_output=True, check=False)  # noqa: S603
        return result.stdout.decode(errors="replace") if result.returncode == 0 else None

    def _clear() -> None:
        _set_private_text("")


# --------------------------------------------------------------------------- public API
def copy_private(text: str, clear_after: int | None = DEFAULT_CLEAR_SECONDS) -> None:
    """Copy ``text`` and schedule its removal after ``clear_after`` seconds."""
    _set_private_text(text)
    if clear_after:
        _spawn_clearer(_digest(text), clear_after)


def clear_if_unchanged(digest: str) -> bool:
    """Wipe the clipboard only if it still holds the text we put there."""
    current = _get_text()
    if current is not None and _digest(current) == digest:
        _clear()
        return True
    return False


def _spawn_clearer(digest: str, seconds: int) -> None:
    args = [sys.executable, "-I", "-m", "quillvault.security.clipboard", digest, str(seconds)]
    if sys.platform == "win32":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(args, creationflags=flags, close_fds=True)  # noqa: S603
    else:
        subprocess.Popen(args, start_new_session=True, close_fds=True)  # noqa: S603


if __name__ == "__main__":  # pragma: no cover - background helper
    _digest_arg, _seconds = sys.argv[1], int(sys.argv[2])
    time.sleep(_seconds)
    clear_if_unchanged(_digest_arg)
