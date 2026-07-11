"""Open canonical local files with the operating system's default app."""

from __future__ import annotations

import os
import platform
import re
import secrets
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

_WSL_TEMP_SUBDIR = "ScholarAIO"
_WSL_TEMP_MAX_AGE_SECONDS = 24 * 60 * 60
_POWERSHELL_TEMP_COMMAND = (
    "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); [System.IO.Path]::GetTempPath()"
)
_POWERSHELL_OPEN_COMMAND = "$ErrorActionPreference = 'Stop'; Start-Process -FilePath $env:SCHOLARAIO_PDF_PATH"


class DefaultApplicationOpenError(RuntimeError):
    """Raised when a local file cannot be launched in its default app."""


@dataclass(frozen=True)
class DefaultApplicationOpenCapability:
    """Describe whether the host can launch files and where they open."""

    enabled: bool
    target: str | None
    reason: str = ""


def _is_wsl() -> bool:
    if platform.system() != "Linux":
        return False
    if os.environ.get("WSL_INTEROP") or os.environ.get("WSL_DISTRO_NAME"):
        return True
    return "microsoft" in platform.release().casefold()


def default_application_open_capability() -> DefaultApplicationOpenCapability:
    """Return the native-launch capability without starting an application."""
    system = platform.system()
    if system == "Windows":
        if getattr(os, "startfile", None) is None:
            return DefaultApplicationOpenCapability(False, None, "Windows default-application launcher is unavailable")
        return DefaultApplicationOpenCapability(True, "host")

    if _is_wsl():
        missing = [name for name in ("powershell.exe", "wslpath") if shutil.which(name) is None]
        if missing:
            return DefaultApplicationOpenCapability(
                False,
                None,
                f"Required WSL Windows bridge launcher(s) not found: {', '.join(missing)}",
            )
        return DefaultApplicationOpenCapability(True, "windows")

    command = "open" if system == "Darwin" else "xdg-open"
    if shutil.which(command) is None:
        return DefaultApplicationOpenCapability(False, None, f"Required desktop launcher `{command}` was not found")
    return DefaultApplicationOpenCapability(True, "host")


def _run_text(args: list[str]) -> str:
    completed = subprocess.run(
        args,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    if not value:
        raise DefaultApplicationOpenError(f"Launcher returned no path: {args[0]}")
    return value


def _safe_temp_pdf_name(path: Path) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", path.name).strip(" .") or "paper.pdf"
    stem = Path(name).stem[:96].strip(" .") or "paper"
    return f"{secrets.token_hex(6)}-{stem}.pdf"


def _cleanup_stale_wsl_pdfs(directory: Path) -> None:
    cutoff = time.time() - _WSL_TEMP_MAX_AGE_SECONDS
    for candidate in directory.glob("*.pdf"):
        try:
            if candidate.is_file() and candidate.stat().st_mtime < cutoff:
                candidate.unlink()
        except OSError:
            continue


def _open_wsl_pdf(path: Path, powershell: str, wslpath: str) -> None:
    windows_temp = _run_text(
        [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", _POWERSHELL_TEMP_COMMAND]
    )
    linux_temp = Path(_run_text([wslpath, "-u", windows_temp])).expanduser()
    managed_temp = linux_temp / _WSL_TEMP_SUBDIR
    managed_temp.mkdir(parents=True, exist_ok=True)
    _cleanup_stale_wsl_pdfs(managed_temp)
    copied_pdf = managed_temp / _safe_temp_pdf_name(path)
    shutil.copyfile(path, copied_pdf)
    windows_pdf = _run_text([wslpath, "-w", str(copied_pdf)])
    child_env = os.environ.copy()
    forwarded = [entry for entry in child_env.get("WSLENV", "").split(":") if entry]
    if not any(entry.split("/", 1)[0] == "SCHOLARAIO_PDF_PATH" for entry in forwarded):
        forwarded.append("SCHOLARAIO_PDF_PATH")
    child_env["WSLENV"] = ":".join(forwarded)
    child_env["SCHOLARAIO_PDF_PATH"] = windows_pdf
    subprocess.run(
        [
            powershell,
            "-NoLogo",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _POWERSHELL_OPEN_COMMAND,
        ],
        check=True,
        capture_output=True,
        env=child_env,
        text=True,
        timeout=10,
    )


def open_with_default_application(path: Path) -> None:
    """Launch an existing file without invoking a command shell."""
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise DefaultApplicationOpenError(f"Path is not an existing file: {resolved}")

    system = platform.system()
    try:
        capability = default_application_open_capability()
        if not capability.enabled:
            raise DefaultApplicationOpenError(capability.reason)

        if system == "Windows":
            startfile = getattr(os, "startfile", None)
            if startfile is None:
                raise DefaultApplicationOpenError("Windows default-application launcher is unavailable")
            startfile(str(resolved))
            return

        if _is_wsl():
            powershell = shutil.which("powershell.exe")
            wslpath = shutil.which("wslpath")
            if powershell is None or wslpath is None:
                raise DefaultApplicationOpenError(capability.reason)
            _open_wsl_pdf(resolved, powershell, wslpath)
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
    except (OSError, subprocess.SubprocessError) as exc:
        raise DefaultApplicationOpenError(f"Could not open file with the default application: {exc}") from exc
