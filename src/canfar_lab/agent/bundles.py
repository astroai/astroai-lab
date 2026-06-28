from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from canfar_lab.agent.bundle_path import bundle_root
from canfar_lab.agent.free_models import apply_free_models, apply_kilo, free_models_guide
from canfar_lab.errors import LabError


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dicts(out[key], val)
        else:
            out[key] = val
    return out


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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
    merged = _merge_dicts(_read_json(dst_json), _read_json(src_json))
    servers = _merge_dicts(
        merged.get("mcpServers", {}),
        _read_json(src_json).get("mcpServers", {}),
    )
    _write_json(dst_json, {"mcpServers": servers})


def merge_claude_json(src_mcp: Path, dst: Path, *, force: bool, dry_run: bool) -> None:
    if not src_mcp.is_file():
        return
    if not dst.is_file():
        install_file(src_mcp, dst, force=True, dry_run=dry_run)
        return
    if dry_run:
        return
    data = _read_json(dst)
    overlay = _read_json(src_mcp)
    data["mcpServers"] = _merge_dicts(data.get("mcpServers", {}), overlay.get("mcpServers", {}))
    _write_json(dst, data)


def merge_opencode_mcp(src: Path, dst: Path, *, force: bool, dry_run: bool) -> None:
    if not src.is_file():
        return
    if not dst.is_file() or force:
        install_file(src, dst, force=True, dry_run=dry_run)
        return
    if dry_run:
        return
    data = _read_json(dst)
    overlay = _read_json(src)
    data["mcp"] = _merge_dicts(data.get("mcp", {}), overlay.get("mcp", {}))
    data["lsp"] = _merge_dicts(data.get("lsp", {}), overlay.get("lsp", {}))
    _write_json(dst, data)


def install_goose_config(root: Path, home: Path, *, force: bool, dry_run: bool) -> None:
    src = root / "goose" / "extensions.yaml"
    dst = home / ".config" / "goose" / "config.yaml"
    if dst.is_file() and not force:
        return
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(f"# CANFAR lab — run: goose configure\n{src.read_text()}", encoding="utf-8")


def install_upstream_skill(
    root: Path,
    home: Path,
    name: str,
    repo: str,
    path: str,
    *,
    force: bool,
    dry_run: bool,
) -> bool:
    dst = home / ".cursor" / "skills" / name
    if (dst / "SKILL.md").is_file() and not force:
        return False
    if dry_run:
        return True
    cache_root = root / ".upstream-cache" / repo.replace("/", "_")
    src = cache_root / path
    if not (cache_root / ".git").is_dir():
        cache_root.parent.mkdir(parents=True, exist_ok=True)
        if cache_root.exists():
            shutil.rmtree(cache_root)
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                f"https://github.com/{repo}.git",
                str(cache_root),
            ],
            check=False,
            capture_output=True,
        )
    else:
        subprocess.run(["git", "-C", str(cache_root), "pull", "--ff-only"], check=False)
    subprocess.run(
        ["git", "-C", str(cache_root), "sparse-checkout", "set", path],
        check=False,
    )
    if not (src / "SKILL.md").is_file():
        return False
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return True


def install_upstream_skills(root: Path, home: Path, *, force: bool, dry_run: bool) -> int:
    sources = root / "skills-sources.json"
    if not sources.is_file():
        return 0
    data = _read_json(sources)
    count = 0
    for item in data.get("upstream_skills", []):
        if install_upstream_skill(
            root,
            home,
            item["name"],
            item["repo"],
            item["path"],
            force=force,
            dry_run=dry_run,
        ):
            count += 1
    return count


def default_bundle_names(root: Path) -> list[str]:
    manifest = root / "manifest.json"
    if manifest.is_file():
        data = _read_json(manifest)
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
        if force or not hook.is_file():
            if not dry_run:
                hook.parent.mkdir(parents=True, exist_ok=True)
                hook.write_text(
                    "# CANFAR lab agent setup — GitHub token for gh + GitHub MCP\n"
                    "if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then\n"
                    '  export GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"\n'
                    "fi\n",
                    encoding="utf-8",
                )
        bashrc = home / ".bashrc"
        marker = "# canfar-lab agent setup"
        if bashrc.exists() and marker not in bashrc.read_text():
            if not dry_run:
                with bashrc.open("a", encoding="utf-8") as fh:
                    fh.write(
                        f"\n{marker}\n"
                        '[[ -f "${HOME}/.config/canfar/lab/agent-env.sh" ]] '
                        '&& source "${HOME}/.config/canfar/lab/agent-env.sh"\n'
                    )
    elif name == "project":
        if project_dir is None:
            raise LabError("Project directory required.", hint="canfar-lab agent project [dir]")
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
        raise LabError(f"Unknown bundle: {name}", hint="canfar-lab agent setup --list")


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
        home / ".canfar" / "lab",
    ]
    if dry_run:
        return
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def write_stamp(home: Path, mode: str, *, dry_run: bool) -> None:
    if dry_run:
        return
    root = bundle_root()
    ver = "unknown"
    version_file = root / "VERSION"
    if version_file.is_file():
        ver = version_file.read_text(encoding="utf-8").strip()
    from datetime import datetime, timezone

    stamp = home / ".canfar" / "lab" / "agent-setup-stamp"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + f" bundle={ver} mode={mode}\n",
        encoding="utf-8",
    )


def verify_setup(home: Path) -> list[str]:
    issues: list[str] = []
    mcp = home / ".cursor" / "mcp.json"
    if not mcp.is_file() or not _read_json(mcp).get("mcpServers"):
        issues.append("MCP not configured (~/.cursor/mcp.json)")
    skill = home / ".cursor" / "skills" / "canfar-lab-workflow" / "SKILL.md"
    if not skill.is_file():
        issues.append("canfar-lab-workflow skill missing")
    return issues


def list_bundles() -> dict[str, str]:
    manifest = bundle_root() / "manifest.json"
    if not manifest.is_file():
        return {}
    data = _read_json(manifest)
    return {k: v.get("description", "") for k, v in data.get("bundles", {}).items()}
