from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from scholaraio.services import system_open


def _pdf(tmp_path: Path) -> Path:
    path = tmp_path / "paper with spaces.pdf"
    path.write_bytes(b"%PDF-test")
    return path


def _set_platform(monkeypatch, name: str, *, release: str = "generic") -> None:
    monkeypatch.setattr(system_open.platform, "system", lambda: name)
    monkeypatch.setattr(system_open.platform, "release", lambda: release)
    monkeypatch.delenv("WSL_DISTRO_NAME", raising=False)
    monkeypatch.delenv("WSL_INTEROP", raising=False)


def test_open_with_default_application_uses_windows_startfile(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    opened: list[str] = []
    _set_platform(monkeypatch, "Windows")
    monkeypatch.setattr(system_open.os, "startfile", lambda path: opened.append(path), raising=False)
    monkeypatch.setattr(
        system_open.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Popen must not run on Windows")),
    )

    system_open.open_with_default_application(pdf)

    assert opened == [str(pdf.resolve())]


@pytest.mark.parametrize(
    ("platform_name", "executable"),
    [("Darwin", "open"), ("Linux", "xdg-open")],
)
def test_open_with_default_application_uses_checked_shell_free_process(
    tmp_path,
    monkeypatch,
    platform_name,
    executable,
):
    pdf = _pdf(tmp_path)
    calls: list[tuple[list[str], dict]] = []
    _set_platform(monkeypatch, platform_name)
    if platform_name == "Linux":
        monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        system_open.subprocess,
        "run",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )

    system_open.open_with_default_application(pdf)

    assert calls == [
        (
            [f"/usr/bin/{executable}", str(pdf.resolve())],
            {
                "check": True,
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "start_new_session": True,
                "close_fds": True,
                "timeout": 10,
            },
        )
    ]


@pytest.mark.parametrize("kind", ["missing", "directory"])
def test_open_with_default_application_rejects_non_files(tmp_path, kind):
    path = tmp_path / "missing.pdf"
    if kind == "directory":
        path.mkdir()

    with pytest.raises(system_open.DefaultApplicationOpenError, match="not an existing file"):
        system_open.open_with_default_application(path)


def test_open_with_default_application_reports_missing_launcher(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    _set_platform(monkeypatch, "Linux")
    monkeypatch.setattr(system_open.shutil, "which", lambda _name: None)

    with pytest.raises(system_open.DefaultApplicationOpenError, match="xdg-open"):
        system_open.open_with_default_application(pdf)


@pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
def test_open_with_default_application_wraps_os_launch_failures(tmp_path, monkeypatch, platform_name):
    pdf = _pdf(tmp_path)
    _set_platform(monkeypatch, platform_name)

    def fail(*_args, **_kwargs):
        raise OSError("desktop session unavailable")

    if platform_name == "Windows":
        monkeypatch.setattr(system_open.os, "startfile", fail, raising=False)
    else:
        if platform_name == "Linux":
            monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr(system_open.subprocess, "run", fail)

    with pytest.raises(system_open.DefaultApplicationOpenError, match="default application") as exc:
        system_open.open_with_default_application(pdf)

    assert "desktop session unavailable" in str(exc.value)


def test_default_application_capability_detects_wsl_windows_bridge(monkeypatch):
    _set_platform(monkeypatch, "Linux", release="6.6.0-microsoft-standard-WSL2")
    monkeypatch.setenv("WSL_INTEROP", "/run/WSL/1_interop")
    launchers = {
        "powershell.exe": "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe",
        "wslpath": "/usr/bin/wslpath",
    }
    monkeypatch.setattr(system_open.shutil, "which", launchers.get)

    capability = system_open.default_application_open_capability()

    assert capability.enabled is True
    assert capability.target == "windows"
    assert capability.reason == ""


def test_default_application_capability_explains_missing_wsl_bridge(monkeypatch):
    _set_platform(monkeypatch, "Linux", release="6.6.0-microsoft-standard-WSL2")
    monkeypatch.setenv("WSL_DISTRO_NAME", "Ubuntu")
    monkeypatch.setattr(system_open, "_WSL_POWERSHELL_CANDIDATES", ())
    monkeypatch.setattr(system_open.shutil, "which", lambda name: None if name == "powershell.exe" else f"/{name}")

    capability = system_open.default_application_open_capability()

    assert capability.enabled is False
    assert capability.target is None
    assert "powershell.exe" in capability.reason


def test_default_application_capability_rejects_headless_linux(monkeypatch):
    _set_platform(monkeypatch, "Linux")
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}")

    capability = system_open.default_application_open_capability()

    assert capability.enabled is False
    assert capability.target is None
    assert "desktop session" in capability.reason.lower()


def test_open_with_default_application_reports_immediate_linux_launcher_failure(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    _set_platform(monkeypatch, "Linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(system_open.subprocess, "Popen", lambda *_args, **_kwargs: None)

    def fail(args, **_kwargs):
        raise subprocess.CalledProcessError(3, args, stderr="no opener")

    monkeypatch.setattr(system_open.subprocess, "run", fail)

    with pytest.raises(system_open.DefaultApplicationOpenError, match="default application"):
        system_open.open_with_default_application(pdf)


@pytest.mark.parametrize(
    ("platform_name", "launcher"),
    [("Windows", None), ("Darwin", "open"), ("Linux", "xdg-open")],
)
def test_default_application_capability_detects_native_desktop(monkeypatch, platform_name, launcher):
    _set_platform(monkeypatch, platform_name)
    if platform_name == "Linux":
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    monkeypatch.setattr(system_open.os, "startfile", lambda _path: None, raising=False)
    monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}" if name == launcher else None)

    capability = system_open.default_application_open_capability()

    assert capability.enabled is True
    assert capability.target == "host"


def test_open_with_default_application_copies_wsl_pdf_to_windows_temp_and_cleans_stale_files(
    tmp_path,
    monkeypatch,
):
    pdf = _pdf(tmp_path)
    os.utime(pdf, (0, 0))
    windows_temp = tmp_path / "windows-temp"
    managed_temp = windows_temp / "ScholarAIO"
    managed_temp.mkdir(parents=True)
    stale = managed_temp / "stale.pdf"
    stale.write_bytes(b"old")
    os.utime(stale, (0, 0))
    _set_platform(monkeypatch, "Linux", release="6.6.0-microsoft-standard-WSL2")
    monkeypatch.setenv("WSL_INTEROP", "/run/WSL/1_interop")
    fallback_powershell = tmp_path / "Windows" / "System32" / "powershell.exe"
    fallback_powershell.parent.mkdir(parents=True)
    fallback_powershell.write_bytes(b"MZ")
    monkeypatch.setattr(system_open, "_WSL_POWERSHELL_CANDIDATES", (fallback_powershell,))
    launchers = {
        "powershell.exe": str(fallback_powershell),
        "wslpath": "/usr/bin/wslpath",
    }
    monkeypatch.setattr(system_open.shutil, "which", lambda name: launchers.get(name) if name == "wslpath" else None)
    monkeypatch.setattr(system_open.secrets, "token_hex", lambda _size: "abc123")
    run_calls: list[list[str]] = []
    run_kwargs: list[dict] = []

    def fake_run(args, **kwargs):
        run_calls.append(args)
        run_kwargs.append(kwargs)
        if args[0] == launchers["powershell.exe"]:
            return subprocess.CompletedProcess(args, 0, stdout="C:\\Users\\Test\\AppData\\Local\\Temp\r\n")
        if args[1] == "-u":
            return subprocess.CompletedProcess(args, 0, stdout=f"{windows_temp}\n")
        copied = next(managed_temp.glob("abc123-*.pdf"))
        return subprocess.CompletedProcess(args, 0, stdout=f"C:\\Temp\\ScholarAIO\\{copied.name}\r\n")

    monkeypatch.setattr(system_open.subprocess, "run", fake_run)

    system_open.open_with_default_application(pdf)

    copied = next(managed_temp.glob("abc123-*.pdf"))
    assert copied.read_bytes() == pdf.read_bytes()
    assert copied.stat().st_mtime > time.time() - 5
    assert stale.exists() is False
    assert [call[1] for call in run_calls[1:3]] == ["-u", "-w"]
    args, kwargs = run_calls[-1], run_kwargs[-1]
    assert args[:5] == [
        launchers["powershell.exe"],
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert args[5] == "$ErrorActionPreference = 'Stop'; Start-Process -FilePath $env:SCHOLARAIO_PDF_PATH"
    assert str(pdf) not in " ".join(args)
    assert kwargs["env"]["SCHOLARAIO_PDF_PATH"] == f"C:\\Temp\\ScholarAIO\\{copied.name}"
    assert "SCHOLARAIO_PDF_PATH" in kwargs["env"]["WSLENV"].split(":")
    assert kwargs["check"] is True
    assert kwargs["timeout"] == 10


def test_wsl_windows_local_app_data_discovers_linux_visible_managed_root(tmp_path, monkeypatch):
    _set_platform(monkeypatch, "Linux", release="6.6.0-microsoft-standard-WSL2")
    monkeypatch.setenv("WSL_INTEROP", "/run/WSL/1_interop")
    launchers = {"powershell.exe": "/mnt/c/Windows/powershell.exe", "wslpath": "/usr/bin/wslpath"}
    monkeypatch.setattr(system_open, "_find_wsl_launcher", lambda name: launchers.get(name))
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == launchers["powershell.exe"]:
            return subprocess.CompletedProcess(args, 0, stdout="C:\\Users\\Test\\AppData\\Local\r\n")
        return subprocess.CompletedProcess(args, 0, stdout=f"{tmp_path / 'AppData' / 'Local'}\n")

    monkeypatch.setattr(system_open.subprocess, "run", fake_run)

    root = system_open.wsl_windows_local_app_data()

    assert root == (tmp_path / "AppData" / "Local").resolve()
    assert "LocalApplicationData" in calls[0][0][-1]
    assert calls[1][0][1:3] == ["-u", "C:\\Users\\Test\\AppData\\Local"]


def test_open_wsl_windows_file_launches_stable_path_without_copying(tmp_path, monkeypatch):
    mirror = tmp_path / "AppData" / "Local" / "ScholarAIO" / "editable-pdfs" / "main" / "sync" / "Paper.pdf"
    mirror.parent.mkdir(parents=True)
    mirror.write_bytes(b"%PDF-stable")
    _set_platform(monkeypatch, "Linux", release="6.6.0-microsoft-standard-WSL2")
    monkeypatch.setenv("WSL_INTEROP", "/run/WSL/1_interop")
    launchers = {"powershell.exe": "/mnt/c/Windows/powershell.exe", "wslpath": "/usr/bin/wslpath"}
    monkeypatch.setattr(system_open, "_find_wsl_launcher", lambda name: launchers.get(name))
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        if args[0] == launchers["wslpath"]:
            return subprocess.CompletedProcess(
                args, 0, stdout="C:\\Users\\Test\\AppData\\Local\\ScholarAIO\\editable-pdfs\\main\\sync\\Paper.pdf\r\n"
            )
        return subprocess.CompletedProcess(args, 0, stdout="")

    monkeypatch.setattr(system_open.subprocess, "run", fake_run)

    system_open.open_wsl_windows_file(mirror)

    assert [call[0][0] for call in calls] == [launchers["wslpath"], launchers["powershell.exe"]]
    assert calls[0][0][1] == "-w"
    launch_args, launch_kwargs = calls[1]
    assert launch_args[-1] == system_open._POWERSHELL_OPEN_COMMAND
    assert launch_kwargs["env"]["SCHOLARAIO_PDF_PATH"].endswith("main\\sync\\Paper.pdf")
    assert list(tmp_path.rglob("*.pdf")) == [mirror]
