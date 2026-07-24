from __future__ import annotations

import json
import os
import shutil
import subprocess
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
from astroai_lab.errors import LabError
from astroai_lab.utils.json_utils import merge_dicts, read_json, read_jsonc, write_json


@dataclass(frozen=True)
class SourceUpdateResult:
    name: str
    repo: str
    status: str
    detail: str = ""


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
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


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
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
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


def _upstream_cache_root(home: Path, repo: str) -> Path:
    return home / ".cache" / "astroai-lab" / "upstream-skills" / repo.replace("/", "_")


def upstream_cache_path(home: Path, repo: str) -> Path:
    return _upstream_cache_root(home, repo)


def _git_run(args: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _clone_upstream_repo(
    cache_root: Path, repo: str, paths: str | list[str]
) -> tuple[str, str]:
    path_list = [paths] if isinstance(paths, str) else list(paths)
    if cache_root.exists():
        shutil.rmtree(cache_root)
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    clone = _git_run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            "--filter=blob:none",
            "--sparse",
            f"https://github.com/{repo}.git",
            str(cache_root),
        ]
    )
    if clone.returncode != 0:
        detail = (clone.stderr or clone.stdout or "clone failed").strip()
        return "failed", detail
    # --no-cone allows file paths (e.g. .cursor/rules/ponytail.mdc), not only dirs.
    sparse = _git_run(
        ["git", "-C", str(cache_root), "sparse-checkout", "set", "--no-cone", *path_list]
    )
    if sparse.returncode != 0:
        detail = (sparse.stderr or sparse.stdout or "sparse-checkout failed").strip()
        return "failed", detail
    return "cloned", repo


def _refresh_upstream_repo(
    cache_root: Path, repo: str, paths: str | list[str]
) -> tuple[str, str]:
    path_list = [paths] if isinstance(paths, str) else list(paths)
    if not (cache_root / ".git").is_dir():
        return _clone_upstream_repo(cache_root, repo, path_list)
    fetch = _git_run(["git", "-C", str(cache_root), "fetch", "--depth", "1", "origin", "HEAD"])
    if fetch.returncode != 0:
        shutil.rmtree(cache_root)
        return _clone_upstream_repo(cache_root, repo, path_list)
    reset = _git_run(["git", "-C", str(cache_root), "reset", "--hard", "FETCH_HEAD"])
    if reset.returncode != 0:
        detail = (reset.stderr or reset.stdout or "reset failed").strip()
        return "failed", detail
    sparse = _git_run(
        ["git", "-C", str(cache_root), "sparse-checkout", "set", "--no-cone", *path_list]
    )
    if sparse.returncode != 0:
        detail = (sparse.stderr or sparse.stdout or "sparse-checkout failed").strip()
        return "failed", detail
    return "updated", repo


def list_github_sources(root: Path | None = None) -> list[dict[str, str]]:
    sources = (root or bundle_root()) / "skills-sources.json"
    if not sources.is_file():
        return []
    data = read_json(sources)
    rows: list[dict[str, str]] = []
    for item in data.get("upstream_skills", []):
        rows.append(
            {
                "name": item["name"],
                "repo": item["repo"],
                "path": item["path"],
                "homepage": item.get("homepage", f"https://github.com/{item['repo']}"),
            }
        )
    return rows


def update_github_source(
    home: Path,
    name: str,
    repo: str,
    path: str,
    *,
    force: bool,
    dry_run: bool,
) -> SourceUpdateResult:
    dst = home / ".cursor" / "skills" / name
    if (dst / "SKILL.md").is_file() and not force:
        return SourceUpdateResult(name, repo, "skipped", "already installed")

    if dry_run:
        return SourceUpdateResult(name, repo, "dry-run", path)

    cache_root = _upstream_cache_root(home, repo)
    status, detail = _refresh_upstream_repo(cache_root, repo, path)
    if status == "failed":
        return SourceUpdateResult(name, repo, status, detail)

    src = cache_root / path
    if not (src / "SKILL.md").is_file():
        return SourceUpdateResult(name, repo, "failed", f"missing SKILL.md at {path}")

    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return SourceUpdateResult(name, repo, status, path)


def update_all_github_sources(
    home: Path | None = None,
    *,
    force: bool = True,
    dry_run: bool = False,
) -> list[SourceUpdateResult]:
    root = bundle_root()
    home = home or Path.home()
    results: list[SourceUpdateResult] = []
    for item in list_github_sources(root):
        results.append(
            update_github_source(
                home,
                item["name"],
                item["repo"],
                item["path"],
                force=force,
                dry_run=dry_run,
            )
        )
    return results


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
    result = update_github_source(home, name, repo, path, force=force, dry_run=dry_run)
    return result.status in {"cloned", "updated", "dry-run"}


def install_upstream_skills(root: Path, home: Path, *, force: bool, dry_run: bool) -> int:
    return sum(
        1
        for r in update_all_github_sources(home, force=force, dry_run=dry_run)
        if r.status in {"cloned", "updated", "dry-run"}
    )


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
            raise LabError("Project directory required.", hint="astroai-lab agent project [dir]")
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
    root = bundle_root()
    ver = "unknown"
    version_file = root / "VERSION"
    if version_file.is_file():
        ver = version_file.read_text(encoding="utf-8").strip()
    from datetime import datetime, timezone

    stamp = home / ".astroai" / "lab" / "agent-setup-stamp"
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + f" bundle={ver} mode={mode}\n",
        encoding="utf-8",
    )


def _rel_home(path: Path, home: Path) -> str:
    try:
        return "~/" + str(path.relative_to(home))
    except ValueError:
        return str(path)


def _check_json_file(path: Path, home: Path, *, jsonc: bool = False) -> str | None:
    """Return a syntax-issue string, or None if the file parses."""
    try:
        if jsonc:
            read_jsonc(path)
        else:
            read_json(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        kind = "JSONC" if jsonc else "JSON"
        return f"{kind} syntax error in {_rel_home(path, home)}: {exc}"
    return None


def _check_toml_file(path: Path, home: Path) -> str | None:
    try:
        import tomllib
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            return None
    try:
        tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return f"TOML syntax error in {_rel_home(path, home)}: {exc}"
    return None


def _check_yaml_file(path: Path, home: Path) -> str | None:
    try:
        import yaml
    except ImportError:
        return None
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as exc:
        return f"YAML syntax error in {_rel_home(path, home)}: {exc}"
    return None


def verify_config_syntax(home: Path) -> list[str]:
    """Parse existing agent config files; report syntax errors only."""
    issues: list[str] = []
    checks: list[tuple[Path, str]] = [
        (home / ".cursor" / "mcp.json", "jsonc"),
        (home / ".claude.json", "json"),
        (home / ".claude" / "settings.json", "json"),
        (home / ".config" / "opencode" / "opencode.json", "jsonc"),
        (home / ".config" / "kilo" / "kilo.jsonc", "jsonc"),
        (home / ".copilot" / "mcp-config.json", "jsonc"),
        (home / ".codex" / "config.toml", "toml"),
        (home / ".marimo.toml", "toml"),
        (home / ".config" / "goose" / "config.yaml", "yaml"),
        (home / ".qoder" / "settings.json", "json"),
    ]
    for path, kind in checks:
        if not path.is_file():
            continue
        if kind == "json":
            err = _check_json_file(path, home, jsonc=False)
        elif kind == "jsonc":
            err = _check_json_file(path, home, jsonc=True)
        elif kind == "toml":
            err = _check_toml_file(path, home)
        else:
            err = _check_yaml_file(path, home)
        if err:
            issues.append(err)
    return issues


def verify_setup(home: Path) -> list[str]:
    """Presence + content checks, then syntax validation of configs that exist."""
    issues: list[str] = []
    # Syntax first — broken configs often look "empty" to content checks.
    issues.extend(verify_config_syntax(home))

    mcp = home / ".cursor" / "mcp.json"
    if mcp.is_file():
        try:
            data = read_jsonc(mcp)
            if isinstance(data, dict) and not data.get("mcpServers"):
                issues.append("Cursor MCP empty (~/.cursor/mcp.json)")
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    else:
        issues.append("Cursor MCP not configured (~/.cursor/mcp.json)")

    skill = home / ".cursor" / "skills" / "astroai-lab-workflow" / "SKILL.md"
    if not skill.is_file():
        issues.append("Cursor astroai-lab-workflow skill missing")

    claude = home / ".claude.json"
    if claude.is_file():
        try:
            data = read_json(claude)
            if not data.get("mcpServers"):
                issues.append("Claude MCP empty (~/.claude.json)")
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    oc = home / ".config" / "opencode" / "opencode.json"
    if oc.is_file():
        try:
            data = read_jsonc(oc)
            if isinstance(data, dict) and not data.get("mcp"):
                issues.append("OpenCode MCP empty (~/.config/opencode/opencode.json)")
        except (OSError, ValueError, json.JSONDecodeError):
            pass

    goose_cfg = home / ".config" / "goose" / "config.yaml"
    if goose_cfg.is_file():
        try:
            text = goose_cfg.read_text(encoding="utf-8")
            if "GOOSE_PROVIDER:" not in text or "GOOSE_MODEL:" not in text:
                issues.append(
                    "Goose provider not fully configured (~/.config/goose/config.yaml)"
                )
        except OSError:
            pass

    marimo = home / ".marimo.toml"
    if marimo.is_file():
        try:
            if "openrouter" not in marimo.read_text(encoding="utf-8"):
                issues.append(
                    "marimo.toml missing OpenRouter config — run: "
                    "astroai-lab agent setup marimo"
                )
        except OSError:
            pass

    return issues


def list_skills_inventory(home: Path | None = None) -> list[dict[str, Any]]:
    """Inventory of bundled + upstream skills and anything already under ~/.cursor/skills."""
    root = bundle_root()
    home = home or Path.home()
    sources_path = root / "skills-sources.json"
    catalog: dict[str, dict[str, Any]] = {}

    if sources_path.is_file():
        data = read_json(sources_path)
        for item in data.get("local_skills", []):
            name = item["name"]
            catalog[name] = {
                "name": name,
                "source": "bundled",
                "repo": "",
                "path": f"cursor/skills/{name}",
                "homepage": "",
                "note": item.get("note", ""),
            }
        for item in data.get("upstream_skills", []):
            name = item["name"]
            catalog[name] = {
                "name": name,
                "source": "github",
                "repo": item["repo"],
                "path": item["path"],
                "homepage": item.get("homepage", f"https://github.com/{item['repo']}"),
                "note": "",
            }
        for name in data.get("pixi_skills_only", []):
            catalog[name] = {
                "name": name,
                "source": "pixi-skills",
                "repo": "",
                "path": "",
                "homepage": data.get("pixi_skills", {}).get(
                    "homepage", "https://github.com/pavelzw/pixi-skills"
                ),
                "note": "install via pixi-skills, not agent skills update",
            }

    skills_dir = home / ".cursor" / "skills"
    installed_names: set[str] = set()
    if skills_dir.is_dir():
        for skill_md in skills_dir.glob("*/SKILL.md"):
            installed_names.add(skill_md.parent.name)

    rows: list[dict[str, Any]] = []
    for name, meta in catalog.items():
        installed = name in installed_names
        rows.append(
            {
                **meta,
                "installed": installed,
                "skill_path": str(skills_dir / name) if installed else "",
            }
        )

    for name in sorted(installed_names - set(catalog)):
        rows.append(
            {
                "name": name,
                "source": "extra",
                "repo": "",
                "path": "",
                "homepage": "",
                "note": "present under ~/.cursor/skills but not in skills-sources.json",
                "installed": True,
                "skill_path": str(skills_dir / name),
            }
        )

    rows.sort(key=lambda r: (0 if r["source"] == "bundled" else 1, r["name"]))
    return rows


def list_bundles() -> dict[str, str]:
    manifest = bundle_root() / "manifest.json"
    if not manifest.is_file():
        return {}
    data = read_json(manifest)
    return {k: v.get("description", "") for k, v in data.get("bundles", {}).items()}


def agent_setup(
    *,
    mode: str = "install",
    bundles: list[str] | None = None,
    project_dir: Path | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> None:
    root = bundle_root()
    home = Path.home()
    names = bundles or default_bundle_names(root)
    if mode == "project":
        names = ["project"]
    ensure_agent_dirs(home, dry_run=dry_run)
    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    for name in names:
        try:
            run_bundle(name, root, home, project_dir, force=force, dry_run=dry_run)
            succeeded.append(name)
        except Exception as exc:  # noqa: BLE001 — catch any bundle failure for partial success
            failed.append((name, str(exc)))
    if failed and not dry_run:
        summary = "; ".join(f"{n}: {e}" for n, e in failed)
        raise LabError(
            f"Partial setup — {len(succeeded)}/{len(names)} bundles OK, "
            f"{len(failed)} failed: {summary}"
        )
    if not dry_run:
        write_stamp(home, mode, dry_run=False)


def agent_sync(*, dry_run: bool = False) -> list[SourceUpdateResult]:
    """Refresh all agent MCP, rules, skills, configs, and GitHub skill sources."""
    root = bundle_root()
    home = Path.home()
    names = default_bundle_names(root)
    ensure_agent_dirs(home, dry_run=dry_run)
    for name in names:
        run_bundle(name, root, home, None, force=True, dry_run=dry_run)
    results = update_all_github_sources(home, force=True, dry_run=dry_run)
    write_stamp(home, "sync", dry_run=dry_run)
    return results


def agent_verify() -> None:
    issues = verify_setup(Path.home())
    if issues:
        raise LabError("Agent setup incomplete:\n  " + "\n  ".join(issues))


def agent_list_bundles() -> dict[str, str]:
    return list_bundles()
