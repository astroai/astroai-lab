from __future__ import annotations

import contextlib
import os
import platform
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from astroai_lab.core.paths import npm_prefix_dir, user_bin_dir
from astroai_lab.errors import LabError
from astroai_lab.shell.session_env import resolve_session_env
from astroai_lab.utils.subprocess import run, run_capture

TOOLS = {
    "node": "Node.js + npm (baked into base image; pixi fallback)",
    "agent": "Cursor Agent",
    "claude": "Claude Code",
    "agy": "Antigravity CLI",
    "copilot": "GitHub Copilot CLI",
    "qoder": "Qoder CLI (qodercli)",
    "hermes": "Hermes Agent (Nous Research)",
    "openclaw": "OpenClaw (openclaw/openclaw)",
    "freebuff": "Freebuff",
    "pi": "Pi Coding Agent",
    "codewhale": "CodeWhale",
    "swival": "Swival",
    "ast-grep": "ast-grep (sg)",
    "hyperfine": "hyperfine",
}

# CLI binary name when it differs from the install tool key.
TOOL_BINARIES = {
    "ast-grep": "sg",
    "qoder": "qodercli",
}


def _bin_dir() -> Path:
    return user_bin_dir()


def _npm_prefix() -> Path:
    return npm_prefix_dir()


def list_tools() -> dict[str, str]:
    return dict(TOOLS)


def tool_binary(name: str) -> str:
    return TOOL_BINARIES.get(name, name)


def tool_on_path(name: str) -> bool:
    binary = tool_binary(name)
    if shutil.which(binary) is not None:
        return True
    session = resolve_session_env(ensure=False)
    candidates = [
        session.astroai_lab_bin_dir / binary,
        session.astroai_lab_npm_prefix / "bin" / binary,
    ]
    return any(path.is_file() and os.access(path, os.X_OK) for path in candidates)


def list_tools_status() -> list[dict[str, object]]:
    """Installable tools with whether their binary is currently available."""
    rows: list[dict[str, object]] = []
    for name, desc in TOOLS.items():
        binary = tool_binary(name)
        rows.append(
            {
                "name": name,
                "binary": binary,
                "description": desc,
                "installed": tool_on_path(name),
            }
        )
    return rows


def _ensure_bin_dir() -> None:
    _bin_dir().mkdir(parents=True, exist_ok=True)


def _session_environ(extra: dict[str, str] | None = None) -> dict[str, str]:
    merged = {**os.environ, **resolve_session_env(ensure=False).exports()}
    if extra:
        merged.update(extra)
    return merged


def _curl_pipe_bash(url: str, *, env: dict[str, str] | None = None) -> None:
    from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

    _require("curl")
    merged = _session_environ(env)
    # Keep curl + bash within INSTALL_TIMEOUT_SEC total (including curl's +5 slack).
    total = max(60, INSTALL_TIMEOUT_SEC)
    curl_budget = max(20, (total - 5) // 3)
    bash_budget = max(30, total - curl_budget - 5)
    try:
        script = subprocess.run(
            ["curl", "-fsSL", "--max-time", str(curl_budget), url],
            capture_output=True,
            check=True,
            env=merged,
            timeout=curl_budget + 5,
        ).stdout
        subprocess.run(
            ["bash"],
            input=script,
            check=True,
            env=merged,
            timeout=bash_budget,
        )
    except subprocess.TimeoutExpired as exc:
        raise LabError(
            f"Install timed out after {total}s fetching {url}",
            hint="Retry later or raise ASTROAI_LAB_AGENT_INSTALL_TIMEOUT",
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (
            (exc.stderr or b"").decode(errors="replace").strip()
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        raise LabError(
            f"Install failed for {url}" + (f": {detail}" if detail else ""),
            hint="Check network / auth, then retry",
        ) from exc


def _link_into_local_bin(src: Path, name: str) -> None:
    if not src.is_file():
        return
    with contextlib.suppress(OSError):
        src.chmod(src.stat().st_mode | 0o111)
    dst = _bin_dir() / name
    try:
        if src.resolve() == dst.resolve():
            return
    except OSError:
        pass
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.symlink_to(src)


def _verify_cmd(cmd: str, *, extra_paths: list[Path] | None = None) -> None:
    if shutil.which(cmd) is not None:
        return
    session = resolve_session_env(ensure=False)
    candidates = [
        session.astroai_lab_bin_dir / cmd,
        session.astroai_lab_npm_prefix / "bin" / cmd,
        *(extra_paths or []),
    ]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return
    raise LabError(f"{cmd} not found on PATH after install — open a new shell")


def _require(cmd: str) -> None:
    if shutil.which(cmd) is None:
        raise LabError(f"{cmd} is required.", hint=f"Install {cmd} or check PATH")


def _gh_release_bin(repo: str, asset: str, binary: str) -> None:
    _require("gh")
    _require("curl")
    run_capture(["gh", "auth", "status"])
    tmp = Path(os.environ.get("TMPDIR", "").strip() or "/tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    run(["gh", "release", "download", "-R", repo, "-p", asset, "-D", str(tmp)])
    archive = tmp / asset
    if asset.endswith(".tar.gz"):
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(tmp)
    elif asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp)
    else:
        raise LabError(f"Unsupported archive: {asset}")
    found = next(tmp.rglob(binary), None)
    if found is None:
        # Some releases name the extracted binary after the asset basename
        # (e.g. codex-x86_64-unknown-linux-musl) instead of the bare name.
        stem = asset.removesuffix(".tar.gz").removesuffix(".zip")
        candidate = tmp / stem
        if candidate.is_file():
            found = candidate
    if found is None:
        raise LabError(f"Binary {binary} not found in {asset}")
    shutil.copy2(found, _bin_dir() / binary)
    with contextlib.suppress(OSError):
        (_bin_dir() / binary).chmod((_bin_dir() / binary).stat().st_mode | 0o111)
    archive.unlink(missing_ok=True)


def install_tool(name: str, *, dry_run: bool = False) -> None:
    if name not in TOOLS:
        raise LabError(f"Unknown tool: {name}", hint="astroai-lab agent install  (or agent list)")
    if dry_run:
        return
    from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

    resolve_session_env(ensure=True)
    _ensure_bin_dir()
    arch = platform.machine()
    npm_timeout = INSTALL_TIMEOUT_SEC

    if name == "node":
        # Node LTS + npm are baked into the base image (astroai-containers), so
        # this is normally a no-op on CANFAR sessions; keep the pixi fallback
        # for bare environments where node is not already on PATH.
        if shutil.which("node") is not None and shutil.which("npm") is not None:
            return
        _require("pixi")
        session = resolve_session_env(ensure=False)
        pixi_bin = session.pixi_home / "bin"
        bin_dir = _bin_dir()
        run(["pixi", "global", "install", "nodejs"], env=_session_environ(), timeout=npm_timeout)
        for cmd in ("node", "npm", "npx"):
            src = pixi_bin / cmd
            if src.is_file():
                (bin_dir / cmd).unlink(missing_ok=True)
                (bin_dir / cmd).symlink_to(src)
        _verify_cmd("node")
        _verify_cmd("npm")
    elif name == "agent":
        _curl_pipe_bash("https://cursor.com/install")
        _link_into_local_bin(Path.home() / ".local" / "bin" / "agent", "agent")
        _verify_cmd("agent")
    elif name == "claude":
        _curl_pipe_bash("https://claude.ai/install.sh")
        _link_into_local_bin(Path.home() / ".local" / "bin" / "claude", "claude")
        _verify_cmd("claude")
    elif name == "agy":
        _curl_pipe_bash("https://antigravity.google/cli/install.sh")
        _link_into_local_bin(Path.home() / ".local" / "bin" / "agy", "agy")
        _verify_cmd("agy")
    elif name == "copilot":
        env = {"PREFIX": str(_npm_prefix()), "CI": "1"}
        with contextlib.suppress(subprocess.CalledProcessError, LabError):
            _curl_pipe_bash("https://gh.io/copilot-install", env=env)
        copilot_bin = _npm_prefix() / "bin" / "copilot"
        if not copilot_bin.is_file() and shutil.which("copilot") is None:
            _require("npm")
            run(
                [
                    "npm",
                    "install",
                    "-g",
                    "--prefix",
                    str(_npm_prefix()),
                    "@github/copilot@latest",
                ],
                env=_session_environ(),
                timeout=npm_timeout,
            )
            copilot_bin = _npm_prefix() / "bin" / "copilot"
        _link_into_local_bin(copilot_bin, "copilot")
        _verify_cmd("copilot", extra_paths=[copilot_bin])
    elif name == "hermes":
        # Nous Research Hermes Agent — self-contained installer (bootstraps its
        # own Python/uv/Node), first-class OpenRouter + headless `hermes -z`.
        _curl_pipe_bash("https://hermes-agent.nousresearch.com/install.sh")
        hermes_src = _bin_dir() / "hermes"
        if not hermes_src.is_file():
            hermes_src = Path.home() / ".local" / "bin" / "hermes"
        if not hermes_src.is_file():
            hermes_src = Path.home() / ".hermes" / "bin" / "hermes"
        _link_into_local_bin(hermes_src, "hermes")
        _verify_cmd("hermes", extra_paths=[hermes_src])
    elif name == "openclaw":
        # Requires Node >= 24.15 — Node 24.18.1 LTS is baked into the base image.
        _require("npm")
        run(
            ["npm", "install", "-g", "--prefix", str(_npm_prefix()), "openclaw@latest"],
            env=_session_environ(),
            timeout=npm_timeout,
        )
        openclaw_bin = _npm_prefix() / "bin" / "openclaw"
        _link_into_local_bin(openclaw_bin, "openclaw")
        _verify_cmd("openclaw", extra_paths=[openclaw_bin])
    elif name == "qoder":
        env = {"XDG_BIN_DIR": str(_bin_dir())}
        with contextlib.suppress(subprocess.CalledProcessError, LabError):
            _curl_pipe_bash("https://qoder.com/install", env=env)
        qoder_src = _bin_dir() / "qodercli"
        if not qoder_src.is_file():
            qoder_src = Path.home() / ".local" / "bin" / "qodercli"
        if qoder_src.is_file():
            _link_into_local_bin(qoder_src, "qodercli")
            # Convenience alias matching the install tool name.
            _link_into_local_bin(qoder_src, "qoder")
        if shutil.which("qodercli") is None and not (_bin_dir() / "qodercli").is_file():
            _require("npm")
            run(
                [
                    "npm",
                    "install",
                    "-g",
                    "--prefix",
                    str(_npm_prefix()),
                    "@qoder-ai/qodercli@latest",
                ],
                env=_session_environ(),
                timeout=npm_timeout,
            )
            npm_bin = _npm_prefix() / "bin" / "qodercli"
            _link_into_local_bin(npm_bin, "qodercli")
            _link_into_local_bin(npm_bin, "qoder")
        _verify_cmd("qodercli")
    elif name in ("freebuff", "pi", "codewhale"):
        _require("npm")
        pkg = {
            "freebuff": "freebuff@latest",
            "pi": "@earendil-works/pi-coding-agent@latest",
            "codewhale": "codewhale@latest",
        }[name]
        run(
            ["npm", "install", "-g", "--prefix", str(_npm_prefix()), pkg],
            env=_session_environ(),
            timeout=npm_timeout,
        )
        _verify_cmd(name if name != "pi" else "pi")
    elif name == "swival":
        _require("uv")
        run(
            ["uv", "tool", "install", "--force", "swival"],
            env=_session_environ(),
            timeout=npm_timeout,
        )
        _verify_cmd("swival")
    elif name == "ast-grep":
        if arch not in ("x86_64", "aarch64"):
            raise LabError(f"Unsupported architecture: {arch}")
        asset = f"app-{arch}-unknown-linux-gnu.zip"
        _gh_release_bin("ast-grep/ast-grep", asset, "sg")
        (_bin_dir() / "ast-grep").unlink(missing_ok=True)
        (_bin_dir() / "ast-grep").symlink_to(_bin_dir() / "sg")
        _verify_cmd("sg")
    elif name == "hyperfine":
        if shutil.which("hyperfine"):
            return
        tag = "v1.19.0"
        try:
            tag_raw = run_capture(
                ["gh", "release", "view", "-R", "sharkdp/hyperfine", "--json", "tagName"],
                timeout=60,
            )
            import json

            tag = json.loads(tag_raw).get("tagName", tag)
        except LabError:
            pass
        asset = f"hyperfine-{tag}-{arch}-unknown-linux-gnu.tar.gz"
        _gh_release_bin("sharkdp/hyperfine", asset, "hyperfine")
        _verify_cmd("hyperfine")


# ---------------------------------------------------------------------------
# Removal (Phase 2: `agent remove`)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RemoveResult:
    target: str
    status: str  # removed | would_remove | error
    detail: str = ""


# npm package name per tool (mirrors the `npm install -g` calls in install_tool).
TOOL_NPM_PACKAGES = {
    "openclaw": "openclaw",
    "copilot": "@github/copilot",
    "qoder": "@qoder-ai/qodercli",
    "freebuff": "freebuff",
    "pi": "@earendil-works/pi-coding-agent",
    "codewhale": "codewhale",
}

# Home-relative config files a tool owns (removed on `agent remove`).
# Registry-driven agents carry their own config.path in agents/*.yaml.
TOOL_CONFIG_PATHS = {
    "copilot": [".copilot/mcp-config.json"],
    "qoder": [".qoder/settings.json"],
    "hermes": [".hermes/config.yaml"],
    "openclaw": [".openclaw/openclaw.json"],
}


def _remove_file(path: Path, target: str, *, dry_run: bool) -> RemoveResult | None:
    """Unlink a file/symlink; None when it doesn't exist."""
    if not (path.exists() or path.is_symlink()):
        return None
    if dry_run:
        return RemoveResult(target, "would_remove", str(path))
    try:
        path.unlink(missing_ok=True)
        return RemoveResult(target, "removed", str(path))
    except OSError as exc:
        return RemoveResult(target, "error", str(exc))


def _remove_tree(path: Path, target: str, *, dry_run: bool) -> RemoveResult | None:
    """Remove a directory tree; None when it doesn't exist."""
    if not path.exists():
        return None
    if dry_run:
        return RemoveResult(target, "would_remove", str(path))
    try:
        shutil.rmtree(path)
        return RemoveResult(target, "removed", str(path))
    except OSError as exc:
        return RemoveResult(target, "error", str(exc))


def uninstall_tool(
    name: str,
    *,
    home: Path | None = None,
    purge: bool = False,
    dry_run: bool = False,
) -> list[RemoveResult]:
    """Uninstall a CLI tool: binaries, config files, plugin files, setup stamps.

    ``--purge`` additionally removes the tool's whole home config dir (e.g.
    ``~/.hermes``, ``~/.openclaw``). Dry-run reports ``would_remove`` without
    touching the filesystem. Returns one result per target.
    """
    if name not in TOOLS:
        raise LabError(f"Unknown tool: {name}", hint="astroai-lab agent list  (or agent catalog)")
    home = home or Path.home()
    results: list[RemoveResult] = []
    binary = tool_binary(name)

    # 1. Binaries from the session bin dir + npm prefix bin.
    for bin_path in (_bin_dir() / binary, _npm_prefix() / "bin" / binary):
        result = _remove_file(bin_path, f"binary:{binary}", dry_run=dry_run)
        if result:
            results.append(result)

    # 2. Best-effort npm uninstall for npm-installed tools (binary removal
    #    above is authoritative; this just cleans the node_modules tree).
    pkg = TOOL_NPM_PACKAGES.get(name)
    if pkg and not dry_run and shutil.which("npm"):
        from astroai_lab.agent.setup_state import INSTALL_TIMEOUT_SEC

        with contextlib.suppress(LabError, subprocess.CalledProcessError, OSError):
            run(
                ["npm", "uninstall", "-g", "--prefix", str(_npm_prefix()), pkg],
                env=_session_environ(),
                timeout=INSTALL_TIMEOUT_SEC,
                quiet=True,  # keep stdout clean for `--json agent remove/wipe`
            )

    # 3. Config files owned by the tool.
    for rel in TOOL_CONFIG_PATHS.get(name, []):
        result = _remove_file(home / rel, f"config:{rel}", dry_run=dry_run)
        if result:
            results.append(result)

    # 4. Plugin-created files (agent-skill addons: ~/.<id>/skills/...).
    plugin_dir = home / f".{name}" / "skills"
    result = _remove_tree(plugin_dir, f"plugins:{plugin_dir}", dry_run=dry_run)
    if result:
        results.append(result)

    # 5. Setup state stamps.
    from astroai_lab.agent.setup_state import failed_path, stamp_path

    for spath, target in (
        (stamp_path(home), "state:stamp"),
        (failed_path(home), "state:failed"),
    ):
        result = _remove_file(spath, target, dry_run=dry_run)
        if result:
            results.append(result)

    # 6. --purge: remove the tool's whole home config dir (parent of config).
    if purge:
        for rel in TOOL_CONFIG_PATHS.get(name, []):
            d = (home / rel).parent
            if d != home:
                result = _remove_tree(d, f"purge:{d}", dry_run=dry_run)
                if result:
                    results.append(result)

    return results
