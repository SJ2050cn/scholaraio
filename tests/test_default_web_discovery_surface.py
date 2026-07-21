"""Contracts for the default host-native web discovery surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from scholaraio.interfaces.cli.parser import _build_parser
from scholaraio.services.setup import _CONFIG_TEMPLATE

ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = ROOT / ".claude" / "skills"


def _subcommand_names(parser: argparse.ArgumentParser) -> set[str]:
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    return set(subparsers.choices)


def test_default_agent_skills_do_not_expose_or_route_to_websearch() -> None:
    assert not (SKILLS_ROOT / "websearch").exists()

    forbidden = ("/websearch", "scholaraio websearch", "guilessbingsearch", "search_bing")
    offenders: list[str] = []
    for path in SKILLS_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8").lower()
        if any(token in text for token in forbidden):
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_default_cli_mcp_and_config_do_not_register_websearch() -> None:
    assert "websearch" not in _subcommand_names(_build_parser())

    mcp_config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))
    assert "web-search" not in mcp_config["mcpServers"]

    default_config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    setup_config = yaml.safe_load(_CONFIG_TEMPLATE)
    assert "websearch" not in default_config
    assert "websearch" not in setup_config


def test_paper2any_mcp_is_explicit_opt_in() -> None:
    mcp_config = json.loads((ROOT / ".mcp.json").read_text(encoding="utf-8"))

    assert "paper2any" not in mcp_config["mcpServers"]


def test_agent_entry_docs_do_not_recommend_websearch() -> None:
    forbidden = ("websearch", "web-search")
    for path in (ROOT / "AGENTS.md", ROOT / "AGENTS_CN.md"):
        text = path.read_text(encoding="utf-8").lower()
        assert not any(token in text for token in forbidden)
