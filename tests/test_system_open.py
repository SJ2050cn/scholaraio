from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from scholaraio.services import system_open


def _pdf(tmp_path: Path) -> Path:
    path = tmp_path / "paper with spaces.pdf"
    path.write_bytes(b"%PDF-test")
    return path


def test_open_with_default_application_uses_windows_startfile(tmp_path, monkeypatch):
    pdf = _pdf(tmp_path)
    opened: list[str] = []
    monkeypatch.setattr(system_open.platform, "system", lambda: "Windows")
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
def test_open_with_default_application_uses_detached_shell_free_process(
    tmp_path,
    monkeypatch,
    platform_name,
    executable,
):
    pdf = _pdf(tmp_path)
    calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(system_open.platform, "system", lambda: platform_name)
    monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        system_open.subprocess,
        "Popen",
        lambda args, **kwargs: calls.append((args, kwargs)),
    )

    system_open.open_with_default_application(pdf)

    assert calls == [
        (
            [f"/usr/bin/{executable}", str(pdf.resolve())],
            {
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
                "start_new_session": True,
                "close_fds": True,
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
    monkeypatch.setattr(system_open.platform, "system", lambda: "Linux")
    monkeypatch.setattr(system_open.shutil, "which", lambda _name: None)

    with pytest.raises(system_open.DefaultApplicationOpenError, match="xdg-open"):
        system_open.open_with_default_application(pdf)


@pytest.mark.parametrize("platform_name", ["Windows", "Darwin", "Linux"])
def test_open_with_default_application_wraps_os_launch_failures(tmp_path, monkeypatch, platform_name):
    pdf = _pdf(tmp_path)
    monkeypatch.setattr(system_open.platform, "system", lambda: platform_name)

    def fail(*_args, **_kwargs):
        raise OSError("desktop session unavailable")

    if platform_name == "Windows":
        monkeypatch.setattr(system_open.os, "startfile", fail, raising=False)
    else:
        monkeypatch.setattr(system_open.shutil, "which", lambda name: f"/usr/bin/{name}")
        monkeypatch.setattr(system_open.subprocess, "Popen", fail)

    with pytest.raises(system_open.DefaultApplicationOpenError, match="default application") as exc:
        system_open.open_with_default_application(pdf)

    assert "desktop session unavailable" in str(exc.value)
