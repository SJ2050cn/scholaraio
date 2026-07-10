"""Open canonical local files with the operating system's default app."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path


class DefaultApplicationOpenError(RuntimeError):
    """Raised when a local file cannot be launched in its default app."""


def open_with_default_application(path: Path) -> None:
    """Launch an existing file without invoking a command shell."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise DefaultApplicationOpenError(f"Path is not an existing file: {resolved}")

    system = platform.system()
    try:
        if system == "Windows":
            startfile = getattr(os, "startfile", None)
            if startfile is None:
                raise DefaultApplicationOpenError("Windows default-application launcher is unavailable")
            startfile(str(resolved))
            return

        command = "open" if system == "Darwin" else "xdg-open"
        executable = shutil.which(command)
        if executable is None:
            raise DefaultApplicationOpenError(f"Required desktop launcher `{command}` was not found")
        subprocess.Popen(
            [executable, str(resolved)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except DefaultApplicationOpenError:
        raise
    except OSError as exc:
        raise DefaultApplicationOpenError(f"Could not open file with the default application: {exc}") from exc
