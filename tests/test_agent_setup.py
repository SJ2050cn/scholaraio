from __future__ import annotations

from pathlib import Path

import pytest

from scholaraio.core.config import Config
from scholaraio.services.agent_setup import (
    apply_agent_setup_plan,
    build_agent_setup_plan,
    format_agent_setup_plan,
    normalize_agents,
)


def _cfg(root: Path) -> Config:
    cfg = Config()
    cfg._root = root
    return cfg


def _repo_root(tmp_path: Path) -> Path:
    root = tmp_path / "scholaraio"
    (root / ".claude" / "skills" / "search").mkdir(parents=True)
    (root / "config.yaml").write_text("paths: {}\n", encoding="utf-8")
    exe = root / ".venv" / "bin" / "scholaraio"
    exe.parent.mkdir(parents=True)
    exe.write_text("#!/bin/sh\n", encoding="utf-8")
    return root


def test_normalize_agents_defaults_to_all_supported_agents():
    agents = normalize_agents(None)

    assert "codex" in agents
    assert "openclaw" in agents
    assert "claude" in agents
    assert "copilot" in agents


def test_build_plan_for_codex_includes_shell_and_global_skill_link(tmp_path):
    root = _repo_root(tmp_path)
    home = tmp_path / "home"

    plan = build_agent_setup_plan(
        _cfg(root),
        agents=["codex"],
        home=home,
        shell_path=home / ".bashrc",
    )

    assert plan.config_path == root / "config.yaml"
    assert plan.executable == root / ".venv" / "bin" / "scholaraio"
    assert [action.kind for action in plan.actions] == ["managed_block", "symlink"]
    assert plan.actions[1].target == home / ".agents" / "skills" / "scholaraio"
    assert plan.actions[1].source == root / ".claude" / "skills"


def test_apply_codex_plan_is_idempotent(tmp_path):
    root = _repo_root(tmp_path)
    home = tmp_path / "home"
    shell = home / ".bashrc"
    shell.parent.mkdir(parents=True)
    shell.write_text("# existing user content\n", encoding="utf-8")

    plan = build_agent_setup_plan(_cfg(root), agents=["codex"], home=home, shell_path=shell)
    applied = apply_agent_setup_plan(plan)
    applied_again = apply_agent_setup_plan(
        build_agent_setup_plan(_cfg(root), agents=["codex"], home=home, shell_path=shell)
    )

    assert (home / ".agents" / "skills" / "scholaraio").resolve() == root / ".claude" / "skills"
    shell_text = shell.read_text(encoding="utf-8")
    assert shell_text.startswith("# existing user content")
    assert shell_text.count("BEGIN ScholarAIO agent setup") == 1
    assert "SCHOLARAIO_CONFIG" in shell_text
    assert {action.status for action in applied.actions} == {"created", "updated"}
    assert {action.status for action in applied_again.actions} == {"already_ok"}


def test_existing_non_link_global_skill_target_blocks_apply(tmp_path):
    root = _repo_root(tmp_path)
    home = tmp_path / "home"
    target = home / ".agents" / "skills" / "scholaraio"
    target.parent.mkdir(parents=True)
    target.write_text("not a link\n", encoding="utf-8")

    plan = build_agent_setup_plan(_cfg(root), agents=["codex"], home=home, shell_path=home / ".bashrc")
    applied = apply_agent_setup_plan(plan)

    blocked = next(action for action in applied.actions if action.kind == "symlink")
    assert blocked.status == "blocked"
    assert target.read_text(encoding="utf-8") == "not a link\n"


def test_symlink_creation_failure_reports_blocked(tmp_path, monkeypatch):
    root = _repo_root(tmp_path)
    home = tmp_path / "home"

    def fail_symlink(*args, **kwargs):
        raise OSError("symlink denied")

    monkeypatch.setattr(Path, "symlink_to", fail_symlink)

    plan = build_agent_setup_plan(
        _cfg(root),
        agents=["codex"],
        home=home,
        shell_path=home / ".bashrc",
        include_shell=False,
    )
    applied = apply_agent_setup_plan(plan)

    symlink = applied.actions[0]
    assert symlink.status == "blocked"
    assert "symlink denied" in symlink.detail


def test_missing_canonical_skills_blocks_skill_registration(tmp_path):
    root = tmp_path / "scholaraio"
    root.mkdir()
    (root / "config.yaml").write_text("paths: {}\n", encoding="utf-8")

    plan = build_agent_setup_plan(
        _cfg(root), agents=["codex"], home=tmp_path / "home", shell_path=tmp_path / "home/.bashrc"
    )

    symlink = next(action for action in plan.actions if action.kind == "symlink")
    assert symlink.status == "blocked"
    assert "canonical skills directory is missing" in symlink.detail


def test_all_mode_marks_claude_as_manual_and_project_hosts_need_target(tmp_path):
    root = _repo_root(tmp_path)

    plan = build_agent_setup_plan(
        _cfg(root), all_agents=True, home=tmp_path / "home", shell_path=tmp_path / "home/.bashrc"
    )

    manual_agents = {action.agent for action in plan.actions if action.status == "manual"}
    assert "claude" in manual_agents
    assert "qwen" in manual_agents
    assert "cursor" in manual_agents
    claude = next(action for action in plan.actions if action.agent == "claude")
    assert "/plugin marketplace add ZimoLiao/scholaraio" in claude.command


def test_target_project_wrappers_are_created_and_preserve_existing_content(tmp_path):
    root = _repo_root(tmp_path)
    project = tmp_path / "project"
    cline_rules = project / ".clinerules"
    cline_rules.parent.mkdir(parents=True)
    cline_rules.write_text("existing cline rule\n", encoding="utf-8")

    plan = build_agent_setup_plan(
        _cfg(root),
        agents=["qwen", "cursor", "cline", "windsurf", "copilot"],
        home=tmp_path / "home",
        shell_path=tmp_path / "home/.bashrc",
        target_project=project,
        include_shell=False,
    )
    applied = apply_agent_setup_plan(plan)

    assert (project / ".qwen" / "QWEN.md").exists()
    assert (project / ".qwen" / "skills").resolve() == root / ".claude" / "skills"
    assert (project / ".cursor" / "rules" / "scholaraio.mdc").exists()
    assert (project / ".windsurfrules").exists()
    assert (project / ".github" / "copilot-instructions.md").exists()
    assert cline_rules.read_text(encoding="utf-8").startswith("existing cline rule")
    assert "BEGIN ScholarAIO agent setup" in cline_rules.read_text(encoding="utf-8")
    assert {action.status for action in applied.actions} == {"created", "updated"}


def test_managed_blocks_update_in_place(tmp_path):
    root = _repo_root(tmp_path)
    home = tmp_path / "home"
    shell = home / ".bashrc"
    old_root = tmp_path / "old"
    shell.parent.mkdir(parents=True)
    shell.write_text(
        "# user\n"
        "# BEGIN ScholarAIO agent setup\n"
        f'export SCHOLARAIO_CONFIG="{old_root / "config.yaml"}"\n'
        "# END ScholarAIO agent setup\n"
        "# after\n",
        encoding="utf-8",
    )

    applied = apply_agent_setup_plan(build_agent_setup_plan(_cfg(root), agents=["codex"], home=home, shell_path=shell))

    text = shell.read_text(encoding="utf-8")
    assert text.count("BEGIN ScholarAIO agent setup") == 1
    assert str(root / "config.yaml") in text
    assert "# user" in text
    assert "# after" in text
    shell_action = next(action for action in applied.actions if action.kind == "managed_block")
    assert shell_action.status == "updated"


def test_format_preview_mentions_apply_command(tmp_path):
    root = _repo_root(tmp_path)
    plan = build_agent_setup_plan(
        _cfg(root), agents=["codex"], home=tmp_path / "home", shell_path=tmp_path / "home/.bashrc"
    )

    rendered = format_agent_setup_plan(plan, mode="preview")

    assert "ScholarAIO agent setup preview" in rendered
    assert "scholaraio setup agent --apply" in rendered


def test_format_preview_marks_manual_actions_separately(tmp_path):
    root = _repo_root(tmp_path)
    plan = build_agent_setup_plan(
        _cfg(root),
        agents=["claude"],
        home=tmp_path / "home",
        include_shell=False,
    )

    rendered = format_agent_setup_plan(plan, mode="preview")

    assert "[manual] claude" in rendered
    assert "[OK] claude" not in rendered
    assert "scholaraio setup agent --apply" not in rendered


def test_project_wrapper_content_warns_about_local_machine_paths(tmp_path):
    root = _repo_root(tmp_path)
    project = tmp_path / "project"

    applied = apply_agent_setup_plan(
        build_agent_setup_plan(
            _cfg(root),
            agents=["cursor"],
            home=tmp_path / "home",
            target_project=project,
            include_shell=False,
        )
    )

    assert {action.status for action in applied.actions} == {"created"}
    content = (project / ".cursor" / "rules" / "scholaraio.mdc").read_text(encoding="utf-8")
    assert "local machine integration" in content
    assert "review before committing" in content
    assert str(root / "config.yaml") in content


def test_invalid_agent_name_raises_value_error():
    with pytest.raises(ValueError):
        normalize_agents(["bad-agent"])


def test_setup_agent_parser_exposes_preview_apply_and_check():
    from scholaraio.interfaces.cli import compat as cli

    parser = cli._build_parser()
    setup_parser = parser._subparsers._group_actions[0].choices["setup"]
    agent_parser = setup_parser._subparsers._group_actions[0].choices["agent"]
    agent_help = agent_parser.format_help()
    check_help = agent_parser._subparsers._group_actions[0].choices["check"].format_help()

    assert "Apply automatic setup actions" in agent_help
    assert "--apply" in agent_help
    assert "--target-project" in agent_help
    assert "--lang" in check_help
    assert "{check}" not in agent_help
    assert "[check]" in agent_help


def test_setup_agent_parser_preserves_parent_flags_for_check():
    from scholaraio.interfaces.cli import compat as cli

    args = cli._build_parser().parse_args(["setup", "agent", "--all", "check"])

    assert args.setup_action == "agent"
    assert args.setup_agent_action == "check"
    assert args.setup_agent_all is True


def test_cmd_setup_agent_preview_does_not_write_files(tmp_path, monkeypatch):
    from argparse import Namespace

    from scholaraio.interfaces.cli.setup import cmd_setup

    root = _repo_root(tmp_path)
    home = tmp_path / "home"
    shell = home / ".bashrc"
    messages: list[str] = []
    monkeypatch.setattr("scholaraio.interfaces.cli.setup._ui", messages.append)

    args = Namespace(
        setup_action="agent",
        setup_agent_action=None,
        agent=["codex"],
        setup_agent_all=False,
        target_project=None,
        shell=str(shell),
        no_shell=False,
        force=False,
        lang="en",
        apply=False,
    )

    cmd_setup(args, _cfg(root))

    assert messages
    assert "ScholarAIO agent setup preview" in messages[0]
    assert not shell.exists()
    assert not (home / ".agents").exists()


def test_cmd_setup_agent_check_renders_zh_status(tmp_path, monkeypatch):
    from argparse import Namespace

    from scholaraio.interfaces.cli.setup import cmd_setup

    root = _repo_root(tmp_path)
    messages: list[str] = []
    monkeypatch.setattr("scholaraio.interfaces.cli.setup._ui", messages.append)

    args = Namespace(
        setup_action="agent",
        setup_agent_action="check",
        agent=["codex"],
        setup_agent_all=False,
        target_project=None,
        shell=str(tmp_path / "home" / ".bashrc"),
        no_shell=False,
        force=False,
        lang="zh",
        apply=False,
    )

    cmd_setup(args, _cfg(root))

    assert "ScholarAIO agent setup 检查" in messages[0]
    assert "配置:" in messages[0]
