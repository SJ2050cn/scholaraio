"""Tests for CLI runtime startup compatibility behavior."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from scholaraio.interfaces.cli import runtime


@dataclass
class _TextStream:
    encoding: str
    errors: str = "strict"
    reconfigure_calls: list[dict[str, str]] = field(default_factory=list)

    def reconfigure(self, **kwargs: str) -> None:
        self.reconfigure_calls.append(kwargs)


class _PlainStream:
    encoding = "cp1252"
    errors = "strict"


class _FailingStream(_TextStream):
    def reconfigure(self, **kwargs: str) -> None:
        raise OSError("stream cannot be reconfigured")


def test_configure_windows_stdio_is_noop_off_windows(monkeypatch):
    stdout = _TextStream("cp1252")
    stderr = _TextStream("cp1252")
    monkeypatch.setattr(runtime, "_is_windows", lambda: False)
    monkeypatch.setattr(runtime.sys, "stdout", stdout)
    monkeypatch.setattr(runtime.sys, "stderr", stderr)

    runtime._configure_windows_stdio()

    assert stdout.reconfigure_calls == []
    assert stderr.reconfigure_calls == []


def test_configure_windows_stdio_respects_explicit_pythonioencoding(monkeypatch):
    stdout = _TextStream("cp1252")
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.setenv("PYTHONIOENCODING", "cp1252:strict")
    monkeypatch.setattr(runtime.sys, "stdout", stdout)
    monkeypatch.setattr(runtime.sys, "stderr", _PlainStream())

    runtime._configure_windows_stdio()

    assert stdout.reconfigure_calls == []


def test_configure_windows_stdio_preserves_encoding_and_replaces_errors(monkeypatch):
    stdout = _TextStream("cp1252")
    stderr = _TextStream("utf-8")
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.setattr(runtime.sys, "stdout", stdout)
    monkeypatch.setattr(runtime.sys, "stderr", stderr)

    runtime._configure_windows_stdio()

    assert stdout.reconfigure_calls == [{"errors": "replace"}]
    assert stderr.reconfigure_calls == []


def test_configure_windows_stdio_prevents_real_cp1252_write_failure(monkeypatch):
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="cp1252", errors="strict")
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.setattr(runtime.sys, "stdout", stdout)
    monkeypatch.setattr(runtime.sys, "stderr", None)

    runtime._configure_windows_stdio()
    stdout.write("中文")
    stdout.flush()

    assert stdout.encoding == "cp1252"
    assert buffer.getvalue() == b"??"


def test_configure_windows_stdio_skips_streams_that_cannot_reconfigure(monkeypatch):
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.setattr(runtime.sys, "stdout", _PlainStream())
    monkeypatch.setattr(runtime.sys, "stderr", None)

    runtime._configure_windows_stdio()


def test_configure_windows_stdio_tolerates_reconfigure_failure(monkeypatch):
    monkeypatch.setattr(runtime, "_is_windows", lambda: True)
    monkeypatch.delenv("PYTHONIOENCODING", raising=False)
    monkeypatch.setattr(runtime.sys, "stdout", _FailingStream("cp1252"))
    monkeypatch.setattr(runtime.sys, "stderr", None)

    runtime._configure_windows_stdio()
