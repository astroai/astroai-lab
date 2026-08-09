"""Agent config writing + setup orchestration.

Extracted from ``bundles.py`` in the Phase 0 decomposition
(docs/agent-rethink-plan.md) — behavior is byte-identical to the original.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from astroai_lab.agent.bundle_path import bundle_root
from astroai_lab.agent.free_models import (
    OPENROUTER_KEY_ENV,
    apply_free_models,
    apply_kilo,
    free_models_guide,
)
from astroai_lab.agent.inventory import list_bundles, verify_setup
from astroai_lab.agent.upstream import (
    SourceUpdateResult,
    install_upstream_skills,
    update_all_github_sources,
)
from astroai_lab.errors import LabError
from astroai_lab.utils.json_utils import merge_dicts, read_json, read_jsonc, write_json


def install_file(src: Path, dst: Path, *, force: bool, dry_run: bool) -> bool:
    if not src.is_file():
        return False
    if dst.is_file() and not force:
        return False
    if dry_run:
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def install_tree(src_dir: Path, dst_dir: Path, *, force: bool, dry_run: bool) -> int:
    if not src_dir.is_dir():
        return 0
    count = 0
    for src in src_dir.rglob("*"):
        if not src.is_file() or src.name == ".DS_Store":
            continue
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        if dst.is_file() and not force:
            continue
        if dry_run:
            count += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        count += 1
    return count


def merge_mcp_servers(src_json: Path, dst_json: Path, *, force: bool, dry_run: bool) -> None:
    if not src_json.is_file():
        return
    if not dst_json.is_file() or force:
        install_file(src_json, dst_json, force=True, dry_run=dry_run)
        return
    if dry_run:
        return
    src_data = read_json(src_json)
    dst_data = read_json(dst_json)
    servers = merge_dicts(dst_data.get("mcpServers", {}), src_data.get("mcpServers", {}))
    write_json(dst_json, {"mcpServers": servers})


def merge_claude_json(src_mcp: Path, dst: Path, *, force: bool, dry_run: bool) -> None:
    if not src_mcp.is_file():
        return
    if not dst.is_file():
        install_file(src_mcp, dst, force=True, dry_run=dry_run)
        return
    if dry_run:
        return
    data = read_json(dst)
    overlay = read_json(src_mcp)
    data["mcpServers"] = merge_dicts(data.get("mcpServers", {}), overlay.get("mcpServers", {}))
    write_json(dst, data)


def merge_opencode_mcp(src: Path, dst: Path, *, force: bool, dry_run: bool) -> None:
    if not src.is_file():
        return
    if not dst.is_file() or force:
        install_file(src, dst, force=True, dry_run=dry_run)
        return
    if dry_run:
        return
    data = read_jsonc(dst)
    if not isinstance(data, dict):
        data = {}
    overlay = read_jsonc(src)
    if not isinstance(overlay, dict):
        overlay = {}
    data["mcp"] = merge_dicts(data.get("mcp", {}), overlay.get("mcp", {}))
    data["lsp"] = merge_dicts(data.get("lsp", {}), overlay.get("lsp", {}))
    write_json(dst, data)


def _toml_get(data: dict[str, Any], *keys: str) -> Any:
    """Walk nested dict keys; return None if any key missing."""
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _merge_marimo_openrouter(cfg: Path, *, force: bool, dry_run: bool) -> None:
    """Ensure ~/.marimo.toml has [ai.openrouter] api_key from OPENROUTER_API_KEY env.

    Merge strategy (never overwrites user settings outside the AI sections):
    1. If file missing, copy template from bundle data.
    2. Check if api_key already set (tomllib).
    3. If not set and env var present, inject api_key under [ai.openrouter].
    """
    root = bundle_root()
    template = root / "marimo" / "marimo.toml"

    if not cfg.is_file() and not dry_run:
        cfg.parent.mkdir(parents=True, exist_ok=True)
        if template.is_file():
            shutil.copy2(template, cfg)
        else:
            cfg.write_text(
                "# Marimo AI assistant — astroai-lab agent setup\n\n"
                "[ai.openrouter]\n"
                'base_url = "https://openrouter.ai/api/v1"\n',
                encoding="utf-8",
            )

    key = os.environ.get(OPENROUTER_KEY_ENV) or os.environ.get("OPENROUTER_KEY")
    if not key:
        return

    # Check if api_key is already set using tomllib (stdlib 3.11+) or tomli
    text = cfg.read_text(encoding="utf-8")
    try:
        import tomllib  # type: ignore
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            tomllib = None  # type: ignore[assignment]

    if tomllib is not None:
        try:
            data = tomllib.loads(text)
            current_key = _toml_get(data, "ai", "openrouter", "api_key")
            if current_key and not force:
                return
        except Exception:  # noqa: BLE001 — tomllib may be absent or TOML unparseable; fall through to line-based merge
            pass

    if dry_run:
        return

    # Line-based merge: find [ai.openrouter] section and insert/update api_key
    section_header = "[ai.openrouter]"
    lines = text.splitlines()
    section_idx: int | None = None
    next_section_idx: int | None = None

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped == section_header:
            section_idx = i
        elif section_idx is not None and stripped.startswith("[") and stripped.endswith("]"):
            next_section_idx = i
            break

    if section_idx is not None:
        # Section exists — look for existing api_key line within the section
        section_end = next_section_idx if next_section_idx is not None else len(lines)
        api_key_idx: int | None = None
        for i in range(section_idx + 1, section_end):
            if lines[i].strip().startswith("api_key"):
                api_key_idx = i
                break

        if api_key_idx is not None:
            if force:
                indent = len(lines[api_key_idx]) - len(lines[api_key_idx].lstrip())
                lines[api_key_idx] = " " * indent + f'api_key = "{key}"'
                cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

        # No api_key yet — insert right after the section header line
        lines.insert(section_idx + 1, f'api_key = "{key}"')
        cfg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        # Section missing — append at end
        sep = "\n\n" if text.rstrip() else "\n"
        cfg.write_text(
            f'{text.rstrip()}{sep}[ai.openrouter]\napi_key = "{key}"\n',
            encoding="utf-8",
        )


def install_goose_config(root: Path, home: Path, *, force: bool, dry_run: bool) -> None:
    src = root / "goose" / "extensions.yaml"
    dst = home / ".config" / "goose" / "config.yaml"
    if dst.is_file() and not force:
        return
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(f"# AstroAI lab — run: goose configure\n{src.read_text()}", encoding="utf-8")


def default_bundle_names(root: Path) -> list[str]:
    manifest = root / "manifest.json"
    if manifest.is_file():
        data = read_json(manifest)
        return list(data.get("bundles", {}).get("all", {}).get("includes", []))
    return ["cursor", "claude", "opencode", "goose", "codex", "copilot", "cli"]


def run_bundle(
    name: str,
    root: Path,
    home: Path,
    project_dir: Path | None,
    *,
    force: bool,
    dry_run: bool,
) -> None:
    if name == "cursor":
        merge_mcp_servers(
            root / "cursor" / "mcp.json",
            home / ".cursor" / "mcp.json",
            force=force,
            dry_run=dry_run,
        )
        install_tree(
            root / "cursor" / "rules",
            home / ".cursor" / "rules",
            force=force,
            dry_run=dry_run,
        )
        install_tree(
            root / "cursor" / "skills",
            home / ".cursor" / "skills",
            force=force,
            dry_run=dry_run,
        )
        install_upstream_skills(root, home, force=force, dry_run=dry_run)
    elif name == "claude":
        merge_claude_json(
            root / "claude" / "mcp.json",
            home / ".claude.json",
            force=force,
            dry_run=dry_run,
        )
        install_file(
            root / "claude" / "settings.json",
            home / ".claude" / "settings.json",
            force=force,
            dry_run=dry_run,
        )
    elif name == "opencode":
        merge_opencode_mcp(
            root / "opencode" / "opencode.json",
            home / ".config" / "opencode" / "opencode.json",
            force=force,
            dry_run=dry_run,
        )
    elif name == "goose":
        install_goose_config(root, home, force=force, dry_run=dry_run)
        install_file(
            root / "goose" / "goosehints",
            home / ".config" / "goose" / ".goosehints",
            force=force,
            dry_run=dry_run,
        )
    elif name == "kilo":
        apply_kilo(home, "coding", force=force, dry_run=dry_run)
    elif name == "cline":
        install_file(
            root / "free-models" / "cline-free.md",
            home / ".config" / "canfar" / "lab" / "cline-free.md",
            force=force,
            dry_run=dry_run,
        )
    elif name == "free-models":
        apply_free_models(home=home, force=force, dry_run=dry_run, skip_cline=True)
        if not dry_run:
            guide = home / ".config" / "canfar" / "lab" / "free-models-guide.txt"
            guide.parent.mkdir(parents=True, exist_ok=True)
            guide.write_text(free_models_guide() + "\n", encoding="utf-8")
    elif name == "codex":
        install_file(
            root / "codex" / "config.toml",
            home / ".codex" / "config.toml",
            force=force,
            dry_run=dry_run,
        )
    elif name == "copilot":
        merge_mcp_servers(
            root / "copilot" / "mcp-config.json",
            home / ".copilot" / "mcp-config.json",
            force=force,
            dry_run=dry_run,
        )
    elif name == "cli":
        install_file(
            root / "cli" / "agent-tools.sh",
            home / ".config" / "canfar" / "lab" / "agent-tools-reminder.sh",
            force=force,
            dry_run=dry_run,
        )
        hook = home / ".config" / "canfar" / "lab" / "agent-env.sh"
        if (force or not hook.is_file()) and not dry_run:
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text(
                "# AstroAI lab agent setup — GitHub token for gh + GitHub MCP\n"
                "if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then\n"
                '  export GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"\n'
                "fi\n",
                encoding="utf-8",
            )
        bashrc = home / ".bashrc"
        marker = "# astroai-lab agent setup"
        if bashrc.exists() and marker not in bashrc.read_text() and not dry_run:
            with bashrc.open("a", encoding="utf-8") as fh:
                fh.write(
                    f"\n{marker}\n"
                    '[[ -f "${HOME}/.config/canfar/lab/agent-env.sh" ]] '
                    '&& source "${HOME}/.config/canfar/lab/agent-env.sh"\n'
                )
    elif name == "marimo":
        _merge_marimo_openrouter(
            home / ".marimo.toml",
            force=force,
            dry_run=dry_run,
        )
    elif name == "project":
        if project_dir is None:
            raise LabError("Project directory required.", hint="astroai-lab agent setup --project")
        merge_mcp_servers(
            root / "project" / ".cursor" / "mcp.json",
            project_dir / ".cursor" / "mcp.json",
            force=force,
            dry_run=dry_run,
        )
        install_tree(
            root / "project" / ".cursor" / "rules",
            project_dir / ".cursor" / "rules",
            force=force,
            dry_run=dry_run,
        )
        install_file(
            root / "project" / "AGENTS.md",
            project_dir / "AGENTS.md",
            force=force,
            dry_run=dry_run,
        )
        install_file(
            root / "goose" / "goosehints",
            project_dir / ".goosehints",
            force=force,
            dry_run=dry_run,
        )
    else:
        raise LabError(f"Unknown bundle: {name}", hint="astroai-lab agent setup --list")


def ensure_agent_dirs(home: Path, *, dry_run: bool) -> None:
    dirs = [
        home / ".cursor" / "rules",
        home / ".cursor" / "skills",
        home / ".config" / "goose",
        home / ".config" / "opencode",
        home / ".config" / "kilo",
        home / ".codex",
        home / ".copilot",
        home / ".claude",
        home / ".config" / "canfar" / "lab",
        home / ".astroai" / "lab",
        home / ".cache" / "astroai-lab",
    ]
    if dry_run:
        return
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def write_stamp(home: Path, mode: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    from astroai_lab.agent.setup_state import record_setup_ok

    record_setup_ok(home, mode=mode)


@dataclass(frozen=True)
class SetupResult:
    """Structured result for agent setup (wizard / --json)."""

    ok: bool
    partial: bool
    mode: str
    actions: tuple[str, ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    stamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "partial": self.partial,
            "mode": self.mode,
            "actions": list(self.actions),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "stamp": self.stamp,
        }

    @property
    def exit_code(self) -> int:
        if self.ok and not self.partial:
            return 0
        if self.partial or self.actions:
            return 2
        return 1


def agent_setup(
    *,
    mode: str = "install",
    bundles: list[str] | None = None,
    project_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
    use_lock: bool = True,
    verify: bool = True,
) -> SetupResult:
    from astroai_lab.agent.setup_state import (
        agent_setup_lock,
        record_setup_failed,
        record_setup_ok,
        stamp_path,
    )
    from astroai_lab.core.paths import quota_used_pct

    root = bundle_root()
    home = Path.home()
    names = bundles or default_bundle_names(root)
    if mode == "project":
        names = ["project"]
        verify = False  # project mode does not install home agent configs

    warnings: list[str] = []
    quota = quota_used_pct(home)
    if quota is not None and quota >= 98 and not force:
        raise LabError(
            f"Home quota {quota}% — refusing agent setup",
            hint="Free space under /arc/home (caches, old envs) or pass --force",
        )
    if quota is not None and quota >= 90:
        warnings.append(f"Home quota {quota}% — agent configs may fill /arc/home")

    def _run() -> SetupResult:
        ensure_agent_dirs(home, dry_run=dry_run)
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        for name in names:
            try:
                run_bundle(name, root, home, project_dir, force=force, dry_run=dry_run)
                succeeded.append(name)
            except Exception as exc:  # noqa: BLE001 — partial success
                failed.append((name, str(exc)))

        actions = [f"bundle:{n}" for n in succeeded]
        errors = [f"{n}: {e}" for n, e in failed]
        partial = bool(succeeded) and bool(failed)
        ok = bool(succeeded) and not failed

        if not dry_run and ok and verify and mode != "project":
            issues = verify_setup(home)
            if issues:
                detail = "verify: " + "; ".join(issues)[:480]
                errors.append(detail)
                partial = True
                ok = False

        if not dry_run and mode != "project":
            if ok:
                record_setup_ok(home, mode=mode)
            else:
                detail = "; ".join(errors) if errors else "no bundles succeeded"
                from datetime import datetime, timezone

                from astroai_lab.agent.setup_state import lab_state_dir

                state = lab_state_dir(home)
                state.mkdir(parents=True, exist_ok=True)
                ver = "unknown"
                version_file = root / "VERSION"
                if version_file.is_file():
                    ver = version_file.read_text(encoding="utf-8").strip()
                stamp_path(home).write_text(
                    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    + f" bundle={ver} mode={mode}\n",
                    encoding="utf-8",
                )
                record_setup_failed(
                    home,
                    exit_code=2 if (partial or succeeded) else 1,
                    detail=detail[:500],
                )

        stamp = None
        sp = stamp_path(home)
        if sp.is_file():
            stamp = sp.read_text(encoding="utf-8").strip()

        return SetupResult(
            ok=ok,
            partial=partial,
            mode=mode,
            actions=tuple(actions),
            errors=tuple(errors),
            warnings=tuple(warnings),
            stamp=stamp,
        )

    if dry_run or not use_lock:
        return _run()
    with agent_setup_lock(home):
        return _run()


def agent_sync(*, dry_run: bool = False) -> list[SourceUpdateResult]:
    """Refresh all agent MCP, rules, skills, configs, and GitHub skill sources."""
    from astroai_lab.agent.setup_state import (
        agent_setup_lock,
        record_setup_failed,
        record_setup_ok,
    )

    root = bundle_root()
    home = Path.home()
    names = default_bundle_names(root)

    def _run() -> list[SourceUpdateResult]:
        ensure_agent_dirs(home, dry_run=dry_run)
        for name in names:
            run_bundle(name, root, home, None, force=True, dry_run=dry_run)
        results = update_all_github_sources(home, force=True, dry_run=dry_run)
        if dry_run:
            return results
        failures = [r for r in results if r.status == "failed"]
        if failures:
            detail = "; ".join(f"{r.name}: {r.detail}" for r in failures)[:500]
            record_setup_failed(home, exit_code=2, detail=detail)
            # Keep last-attempt stamp without clearing the failed marker.
            stamp_path = home / ".astroai" / "lab" / "agent-setup-stamp"
            stamp_path.parent.mkdir(parents=True, exist_ok=True)
            from datetime import datetime, timezone

            ver = "unknown"
            version_file = root / "VERSION"
            if version_file.is_file():
                ver = version_file.read_text(encoding="utf-8").strip()
            stamp_path.write_text(
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                + f" bundle={ver} mode=sync\n",
                encoding="utf-8",
            )
        else:
            record_setup_ok(home, mode="sync")
        return results

    if dry_run:
        return _run()
    with agent_setup_lock(home):
        return _run()


def agent_verify() -> None:
    issues = verify_setup(Path.home())
    if issues:
        raise LabError("Agent setup incomplete:\n  " + "\n  ".join(issues))


def agent_list_bundles() -> dict[str, str]:
    return list_bundles()
