"""Agent integration setup helpers.

This module owns cross-project agent setup planning and application.  The CLI
renders the plan; this service keeps the filesystem behavior testable and
idempotent.
"""

from __future__ import annotations

import os
import shlex
import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from scholaraio.core.config import Config

Lang = str
AgentName = Literal["codex", "openclaw", "claude", "qwen", "cursor", "cline", "windsurf", "copilot"]
ActionKind = Literal["symlink", "managed_block", "manual"]
ActionStatus = Literal["pending", "already_ok", "created", "updated", "manual", "blocked", "skipped"]

SUPPORTED_AGENT_NAMES: tuple[str, ...] = (
    "codex",
    "openclaw",
    "claude",
    "qwen",
    "cursor",
    "cline",
    "windsurf",
    "copilot",
)

DEFAULT_AGENT_SELECTION: tuple[str, ...] = SUPPORTED_AGENT_NAMES
SHELL_BEGIN = "# BEGIN ScholarAIO agent setup"
SHELL_END = "# END ScholarAIO agent setup"
TEXT_BEGIN = "<!-- BEGIN ScholarAIO agent setup -->"
TEXT_END = "<!-- END ScholarAIO agent setup -->"


@dataclass(frozen=True)
class AgentSetupAction:
    """One planned agent setup operation."""

    agent: str
    kind: ActionKind
    title: str
    status: ActionStatus
    detail: str
    target: Path | None = None
    source: Path | None = None
    begin_marker: str = ""
    end_marker: str = ""
    content: str = ""
    command: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"already_ok", "created", "updated", "skipped"}


@dataclass(frozen=True)
class AgentSetupPlan:
    """A complete setup plan for one command invocation."""

    root: Path
    config_path: Path
    skills_dir: Path
    executable: Path | None
    agents: tuple[str, ...]
    target_project: Path | None
    shell_path: Path | None
    actions: tuple[AgentSetupAction, ...] = field(default_factory=tuple)

    @property
    def has_blocked_actions(self) -> bool:
        return any(action.status == "blocked" for action in self.actions)


def normalize_agents(agents: list[str] | tuple[str, ...] | None = None, *, all_agents: bool = False) -> tuple[str, ...]:
    """Return a stable list of requested agent targets."""
    if all_agents or not agents:
        return DEFAULT_AGENT_SELECTION
    normalized: list[str] = []
    for raw in agents:
        name = raw.strip().lower()
        if name == "all":
            return DEFAULT_AGENT_SELECTION
        if name not in SUPPORTED_AGENT_NAMES:
            raise ValueError(f"unsupported agent target: {raw}")
        if name not in normalized:
            normalized.append(name)
    return tuple(normalized)


def build_agent_setup_plan(
    cfg: Config,
    *,
    agents: list[str] | tuple[str, ...] | None = None,
    all_agents: bool = False,
    target_project: Path | str | None = None,
    shell_path: Path | str | None = None,
    include_shell: bool = True,
    home: Path | str | None = None,
    executable: Path | str | None = None,
) -> AgentSetupPlan:
    """Build a non-mutating plan for cross-project agent setup."""
    selected_agents = normalize_agents(agents, all_agents=all_agents)
    root = cfg._root.resolve()
    config_path = (root / "config.yaml").resolve()
    skills_dir = (root / ".claude" / "skills").resolve()
    home_path = Path(home).expanduser().resolve() if home is not None else Path.home()
    target_path = Path(target_project).expanduser().resolve() if target_project else None
    shell = _resolve_shell_path(shell_path, home_path) if include_shell else None
    exe = Path(executable).expanduser().resolve() if executable is not None else _resolve_executable(root)

    actions: list[AgentSetupAction] = []
    if include_shell and shell is not None:
        actions.append(_plan_shell_action(shell, config_path, exe))

    if "codex" in selected_agents or "openclaw" in selected_agents:
        actions.append(
            _plan_symlink_action(
                agent="codex/openclaw",
                title="Register ScholarAIO skills for Codex/OpenClaw",
                target=home_path / ".agents" / "skills" / "scholaraio",
                source=skills_dir,
                missing_source_detail="canonical skills directory is missing; expected .claude/skills",
            )
        )

    if "claude" in selected_agents:
        actions.append(
            AgentSetupAction(
                agent="claude",
                kind="manual",
                title="Install Claude Code plugin",
                status="manual",
                detail="run these slash commands inside Claude Code, then restart the session",
                command="/plugin marketplace add ZimoLiao/scholaraio\n/plugin install scholaraio@scholaraio-marketplace",
            )
        )

    project_hosts = [name for name in selected_agents if name in {"qwen", "cursor", "cline", "windsurf", "copilot"}]
    if project_hosts:
        if target_path is None:
            for name in project_hosts:
                actions.append(
                    AgentSetupAction(
                        agent=name,
                        kind="manual",
                        title=f"Prepare {display_agent_name(name)} project wrapper",
                        status="manual",
                        detail="pass --target-project <path> to create or update project-local wrapper files",
                    )
                )
        else:
            actions.extend(_project_wrapper_actions(project_hosts, target_path, skills_dir, config_path))

    return AgentSetupPlan(
        root=root,
        config_path=config_path,
        skills_dir=skills_dir,
        executable=exe,
        agents=selected_agents,
        target_project=target_path,
        shell_path=shell,
        actions=tuple(actions),
    )


def apply_agent_setup_plan(plan: AgentSetupPlan, *, force: bool = False) -> AgentSetupPlan:
    """Apply every actionable operation in *plan* and return updated statuses."""
    applied = [_apply_action(action, force=force) for action in plan.actions]
    return replace(plan, actions=tuple(applied))


def format_agent_setup_plan(plan: AgentSetupPlan, *, lang: Lang = "en", mode: str = "preview") -> str:
    """Render an agent setup plan or result for CLI output."""
    lines: list[str] = []
    if lang == "zh":
        heading = {
            "preview": "ScholarAIO agent setup 预览（未修改文件）",
            "apply": "ScholarAIO agent setup 结果",
            "check": "ScholarAIO agent setup 检查",
        }.get(mode, "ScholarAIO agent setup")
        lines.append(heading)
        lines.append(f"  配置: {plan.config_path}")
        if plan.executable is not None:
            lines.append(f"  命令: {plan.executable}")
        if plan.target_project is not None:
            lines.append(f"  目标项目: {plan.target_project}")
            lines.append("  注意: 项目 wrapper 包含本机路径，提交到共享仓库前请先确认。")
    else:
        heading = {
            "preview": "ScholarAIO agent setup preview (no files changed)",
            "apply": "ScholarAIO agent setup result",
            "check": "ScholarAIO agent setup check",
        }.get(mode, "ScholarAIO agent setup")
        lines.append(heading)
        lines.append(f"  config: {plan.config_path}")
        if plan.executable is not None:
            lines.append(f"  command: {plan.executable}")
        if plan.target_project is not None:
            lines.append(f"  target project: {plan.target_project}")
            lines.append("  note: project wrappers contain local machine paths; review before committing them.")

    lines.append("")
    max_agent = max((len(action.agent) for action in plan.actions), default=5)
    for action in plan.actions:
        mark = _status_mark(action.status)
        target = f" -> {action.target}" if action.target is not None else ""
        lines.append(f"  {mark} {action.agent:<{max_agent}}  {action.title}{target}")
        if action.detail:
            lines.append(f"      {action.detail}")
        if action.command:
            for command_line in action.command.splitlines():
                lines.append(f"      {command_line}")

    if mode == "preview" and any(action.status == "pending" for action in plan.actions):
        if lang == "zh":
            lines.append("")
            lines.append("使用 `scholaraio setup agent --apply` 执行可自动完成的步骤。")
        else:
            lines.append("")
            lines.append("Run `scholaraio setup agent --apply` to perform the automatic actions.")

    if any(action.status in {"created", "updated"} for action in plan.actions):
        lines.append("")
        lines.append(
            "Restart your agent session so newly registered skills are discovered."
            if lang != "zh"
            else "请重启 agent 会话，让新注册的 skills 被重新发现。"
        )

    return "\n".join(lines)


def display_agent_name(name: str) -> str:
    return {
        "codex": "Codex",
        "openclaw": "OpenClaw",
        "claude": "Claude Code",
        "qwen": "Qwen",
        "cursor": "Cursor",
        "cline": "Cline",
        "windsurf": "Windsurf",
        "copilot": "GitHub Copilot",
    }.get(name, name)


def _resolve_executable(root: Path) -> Path | None:
    candidates = [
        root / ".venv" / "bin" / "scholaraio",
        root / ".venv" / "Scripts" / "scholaraio.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    found = shutil.which("scholaraio")
    if found:
        return Path(found).resolve()
    return None


def _resolve_shell_path(shell_path: Path | str | None, home: Path) -> Path | None:
    if shell_path:
        return Path(shell_path).expanduser().resolve()
    shell_name = Path(os.environ.get("SHELL", "")).name
    if shell_name == "zsh":
        return home / ".zshrc"
    return home / ".bashrc"


def _plan_shell_action(shell_path: Path, config_path: Path, executable: Path | None) -> AgentSetupAction:
    content_lines = [
        "# Managed by `scholaraio setup agent`.",
        f"export SCHOLARAIO_CONFIG={_shell_quote(config_path)}",
    ]
    detail = "sets SCHOLARAIO_CONFIG"
    if executable is not None:
        content_lines.append(f"export PATH={_shell_quote(executable.parent)}:$PATH")
        detail = "sets SCHOLARAIO_CONFIG and places the ScholarAIO command on PATH"
    else:
        content_lines.append("# ScholarAIO command was not found; install the package or activate its venv.")
        detail = "sets SCHOLARAIO_CONFIG; ScholarAIO command path was not found"
    content = "\n".join(content_lines)
    return _plan_managed_block_action(
        agent="runtime",
        title="Configure shell for cross-project ScholarAIO CLI use",
        target=shell_path,
        begin=SHELL_BEGIN,
        end=SHELL_END,
        content=content,
        detail=detail,
    )


def _project_wrapper_actions(
    hosts: list[str],
    target_project: Path,
    skills_dir: Path,
    config_path: Path,
) -> list[AgentSetupAction]:
    actions: list[AgentSetupAction] = []
    for host in hosts:
        if host == "qwen":
            actions.append(
                _plan_managed_block_action(
                    agent="qwen",
                    title="Create/update Qwen project context",
                    target=target_project / ".qwen" / "QWEN.md",
                    begin=TEXT_BEGIN,
                    end=TEXT_END,
                    content=_wrapper_content("Qwen", skills_dir, config_path),
                    detail="project-local Qwen context that points to ScholarAIO skills and CLI",
                    prefix="# ScholarAIO for Qwen\n\n",
                )
            )
            actions.append(
                _plan_symlink_action(
                    agent="qwen",
                    title="Expose ScholarAIO skills to Qwen",
                    target=target_project / ".qwen" / "skills",
                    source=skills_dir,
                    missing_source_detail="canonical skills directory is missing; expected .claude/skills",
                )
            )
        elif host == "cursor":
            actions.append(
                _plan_managed_block_action(
                    agent="cursor",
                    title="Create/update Cursor project rule",
                    target=target_project / ".cursor" / "rules" / "scholaraio.mdc",
                    begin=TEXT_BEGIN,
                    end=TEXT_END,
                    content=_wrapper_content("Cursor", skills_dir, config_path),
                    detail="Cursor project rule that routes ScholarAIO work to the shared skills and CLI",
                    prefix=("---\ndescription: ScholarAIO cross-project instructions\nalwaysApply: false\n---\n\n"),
                )
            )
        elif host == "cline":
            actions.append(
                _plan_managed_block_action(
                    agent="cline",
                    title="Create/update Cline rules",
                    target=target_project / ".clinerules",
                    begin=TEXT_BEGIN,
                    end=TEXT_END,
                    content=_wrapper_content("Cline", skills_dir, config_path),
                    detail="Cline rules that point ScholarAIO work to the shared skills and CLI",
                )
            )
        elif host == "windsurf":
            actions.append(
                _plan_managed_block_action(
                    agent="windsurf",
                    title="Create/update Windsurf rules",
                    target=target_project / ".windsurfrules",
                    begin=TEXT_BEGIN,
                    end=TEXT_END,
                    content=_wrapper_content("Windsurf", skills_dir, config_path),
                    detail="Windsurf rules that point ScholarAIO work to the shared skills and CLI",
                )
            )
        elif host == "copilot":
            actions.append(
                _plan_managed_block_action(
                    agent="copilot",
                    title="Create/update GitHub Copilot instructions",
                    target=target_project / ".github" / "copilot-instructions.md",
                    begin=TEXT_BEGIN,
                    end=TEXT_END,
                    content=_wrapper_content("GitHub Copilot", skills_dir, config_path),
                    detail="Copilot instructions that point ScholarAIO work to the shared skills and CLI",
                )
            )
    return actions


def _wrapper_content(agent_label: str, skills_dir: Path, config_path: Path) -> str:
    return (
        f"ScholarAIO integration for {agent_label}.\n\n"
        "- Use the `scholaraio` CLI for literature search, reading, ingest, citation, writing, and scientific workflows.\n"
        "- This is a local machine integration block; review before committing it to a shared repository.\n"
        f"- Use `SCHOLARAIO_CONFIG={config_path}` when running ScholarAIO from this project.\n"
        f"- For matching workflows, read the relevant skill under `{skills_dir}` before calling the CLI.\n"
        "- Treat paper conclusions as claims; compare evidence and keep user-facing outputs in the requested project/workspace."
    )


def _plan_symlink_action(
    *,
    agent: str,
    title: str,
    target: Path,
    source: Path,
    missing_source_detail: str,
) -> AgentSetupAction:
    if not source.exists():
        return AgentSetupAction(
            agent=agent,
            kind="symlink",
            title=title,
            status="blocked",
            detail=missing_source_detail,
            target=target,
            source=source,
        )
    if target.is_symlink():
        current = target.resolve(strict=False)
        if current == source.resolve(strict=False):
            return AgentSetupAction(
                agent=agent,
                kind="symlink",
                title=title,
                status="already_ok",
                detail="link already points to the canonical ScholarAIO skills directory",
                target=target,
                source=source,
            )
        return AgentSetupAction(
            agent=agent,
            kind="symlink",
            title=title,
            status="blocked",
            detail=f"existing symlink points to {current}; use --force to replace symlinks only",
            target=target,
            source=source,
        )
    if target.exists():
        return AgentSetupAction(
            agent=agent,
            kind="symlink",
            title=title,
            status="blocked",
            detail="target already exists and is not a ScholarAIO-managed symlink",
            target=target,
            source=source,
        )
    return AgentSetupAction(
        agent=agent,
        kind="symlink",
        title=title,
        status="pending",
        detail=f"will link to {source}",
        target=target,
        source=source,
    )


def _plan_managed_block_action(
    *,
    agent: str,
    title: str,
    target: Path,
    begin: str,
    end: str,
    content: str,
    detail: str,
    prefix: str = "",
) -> AgentSetupAction:
    block = _managed_block(begin, end, content)
    if target.exists() and target.is_dir():
        return AgentSetupAction(
            agent=agent,
            kind="managed_block",
            title=title,
            status="blocked",
            detail="target exists as a directory",
            target=target,
            begin_marker=begin,
            end_marker=end,
            content=content,
        )
    if target.exists():
        existing = target.read_text(encoding="utf-8")
        if block in existing:
            return AgentSetupAction(
                agent=agent,
                kind="managed_block",
                title=title,
                status="already_ok",
                detail=detail,
                target=target,
                begin_marker=begin,
                end_marker=end,
                content=content,
            )
        if begin in existing and end in existing:
            status_detail = f"{detail}; will update existing managed block"
        else:
            status_detail = f"{detail}; will append managed block"
    else:
        status_detail = f"{detail}; will create file"
    return AgentSetupAction(
        agent=agent,
        kind="managed_block",
        title=title,
        status="pending",
        detail=status_detail,
        target=target,
        begin_marker=begin,
        end_marker=end,
        content=(prefix + block if not target.exists() and prefix else content),
    )


def _apply_action(action: AgentSetupAction, *, force: bool) -> AgentSetupAction:
    if action.status in {"already_ok", "manual", "blocked", "skipped"}:
        if not (force and action.kind == "symlink" and action.target and action.target.is_symlink() and action.source):
            return action
    if action.kind == "symlink":
        return _apply_symlink_action(action, force=force)
    if action.kind == "managed_block":
        return _apply_managed_block_action(action)
    return action


def _apply_symlink_action(action: AgentSetupAction, *, force: bool) -> AgentSetupAction:
    if action.target is None or action.source is None:
        return replace(action, status="blocked", detail="missing symlink source or target")
    if not action.source.exists():
        return replace(action, status="blocked", detail="source skills directory is missing")
    if action.target.is_symlink():
        if action.target.resolve(strict=False) == action.source.resolve(strict=False):
            return replace(
                action, status="already_ok", detail="link already points to the canonical ScholarAIO skills directory"
            )
        if not force:
            return action
        action.target.unlink()
    elif action.target.exists():
        return replace(action, status="blocked", detail="target already exists and is not a symlink")
    action.target.parent.mkdir(parents=True, exist_ok=True)
    try:
        action.target.symlink_to(action.source, target_is_directory=True)
    except OSError as exc:
        return replace(action, status="blocked", detail=f"could not create symlink: {exc}")
    return replace(action, status="created", detail=f"linked to {action.source}")


def _apply_managed_block_action(action: AgentSetupAction) -> AgentSetupAction:
    if action.target is None:
        return replace(action, status="blocked", detail="missing target file")
    if action.target.exists() and action.target.is_dir():
        return replace(action, status="blocked", detail="target exists as a directory")
    action.target.parent.mkdir(parents=True, exist_ok=True)
    begin = action.begin_marker
    end = action.end_marker
    if begin not in action.content and end not in action.content:
        block = _managed_block(begin, end, action.content)
    else:
        block = action.content
    if not action.target.exists():
        action.target.write_text(block.rstrip() + "\n", encoding="utf-8")
        return replace(action, status="created", detail="created managed file")

    existing = action.target.read_text(encoding="utf-8")
    if block in existing:
        return replace(action, status="already_ok", detail="managed block already present")
    if begin in existing and end in existing:
        updated = _replace_managed_block(existing, begin, end, block)
        detail = "updated managed block"
    else:
        separator = "\n\n" if existing and not existing.endswith("\n\n") else ""
        updated = existing + separator + block.rstrip() + "\n"
        detail = "appended managed block"
    action.target.write_text(updated, encoding="utf-8")
    return replace(action, status="updated", detail=detail)


def _managed_block(begin: str, end: str, content: str) -> str:
    return f"{begin}\n{content.rstrip()}\n{end}\n"


def _replace_managed_block(text: str, begin: str, end: str, block: str) -> str:
    start = text.index(begin)
    end_index = text.index(end, start) + len(end)
    suffix_start = end_index
    if suffix_start < len(text) and text[suffix_start] == "\n":
        suffix_start += 1
    return text[:start] + block.rstrip() + "\n" + text[suffix_start:]


def _status_mark(status: ActionStatus) -> str:
    if status in {"already_ok", "created", "updated"}:
        return "[OK]"
    if status == "manual":
        return "[manual]"
    if status == "skipped":
        return "[skip]"
    if status == "pending":
        return "[..]"
    return "[--]"


def _shell_quote(path: Path) -> str:
    return shlex.quote(str(path))
