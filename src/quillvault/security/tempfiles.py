"""Private temporary directories that are always removed."""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


def _force_remove(_func: object, path: str, _exc: object) -> None:
    os.chmod(path, stat.S_IWRITE)  # noqa: PTH101 - read-only files on Windows
    Path(path).unlink(missing_ok=True)


def remove_tree(path: Path, attempts: int = 5) -> None:
    """Delete ``path`` recursively, retrying while Windows still holds file handles."""
    for attempt in range(attempts):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onexc=_force_remove)
        except OSError:
            time.sleep(0.2 * (attempt + 1))
        else:
            return


_OWNER_FILE = ".owner-pid"


def _process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes  # noqa: PLC0415

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def make_private_dir(prefix: str = "quillvault-") -> Path:
    """Create a directory only the current user can read (mode 0700 on POSIX).

    The owning process id is recorded so that leftovers from a crashed or killed
    session can be found and removed by :func:`purge_stale_dirs`.
    """
    path = Path(tempfile.mkdtemp(prefix=prefix))
    (path / _OWNER_FILE).write_text(str(os.getpid()), encoding="ascii")
    return path


def purge_stale_dirs(prefix: str = "quillvault-", max_age_hours: float = 12.0) -> int:
    """Delete private dirs left behind by sessions that no longer run.

    A hard kill (Task Manager, closed terminal) skips ``atexit`` handlers, so the
    next start cleans up. Returns the number of directories removed.
    """
    removed = 0
    for candidate in Path(tempfile.gettempdir()).glob(f"{prefix}*"):
        if not candidate.is_dir():
            continue
        owner = candidate / _OWNER_FILE
        try:
            pid = int(owner.read_text(encoding="ascii"))
        except (OSError, ValueError):
            age_hours = (time.time() - candidate.stat().st_mtime) / 3600
            if age_hours < max_age_hours:
                continue  # unknown owner and recent: leave it alone
            pid = -1
        if pid != os.getpid() and not _process_alive(pid):
            remove_tree(candidate)
            removed += not candidate.exists()
    return removed


@contextmanager
def private_tempdir(prefix: str = "quillvault-") -> Iterator[Path]:
    """Context manager around :func:`make_private_dir` that always cleans up.

    Deleting a file does not wipe it from an SSD; full-disk encryption
    (BitLocker / LUKS) is the real protection for data at rest.
    """
    path = make_private_dir(prefix)
    try:
        yield path
    finally:
        remove_tree(path)
