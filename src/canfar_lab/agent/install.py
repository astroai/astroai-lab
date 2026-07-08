from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from canfar_lab.core.paths import npm_prefix_dir, user_bin_dir
from canfar_lab.errors import LabError
from canfar_lab.shell.session_env import resolve_session_env
from canfar_lab.utils.subprocess import run, run_capture

TOOLS = {
    "node": "Node.js + npm (pixi global)",
    "agent": "Cursor Agent",
    "claude": "Claude Code",
    "agy": "Antigravity CLI",
    "opencode": "OpenCode",
    "codex": "Codex CLI",
    "copilot": "GitHub Copilot CLI",
    "goose": "Goose",
    "kilo": "Kilo CLI (@kilocode/cli)",
    "cline": "Cline CLI",
    "freebuff": "Freebuff",
    "pi": "Pi Coding Agent",
    "codewhale": "CodeWhale",
    "swival": "Swival",
    "ast-grep": "ast-grep (sg)",
    "hyperfine": "hyperfine",
}


def _bin_dir() -> Path:
    return user_bin_dir()


def _npm_prefix() -> Path:
    return npm_prefix_dir()


def list_tools() -> dict[str, str]:
    return dict(TOOLS)


def _ensure_bin_dir() -> None:
    _bin_dir().mkdir(parents=True, exist_ok=True)


def _session_environ(extra: dict[str, str] | None = None) -> dict[str, str]:
    merged = {**os.environ, **resolve_session_env(ensure=False).exports()}
    if extra:
        merged.update(extra)
    return merged


def _curl_pipe_bash(url: str, *, env: dict[str, str] | None = None) -> None:
    _require("curl")
    merged = _session_environ(env)
    script = subprocess.run(
        ["curl", "-fsSL", url],
        capture_output=True,
        check=True,
        env=merged,
    ).stdout
    subprocess.run(["bash"], input=script, check=True, env=merged)


def _link_into_local_bin(src: Path, name: str) -> None:
    if not src.is_file():
        return
    try:
        src.chmod(src.stat().st_mode | 0o111)
    except OSError:
        pass
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
        session.canfar_lab_bin_dir / cmd,
        session.canfar_lab_npm_prefix / "bin" / cmd,
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
    tmp = Path(os.environ.get("TMPDIR", "/tmp"))
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
        raise LabError(f"Binary {binary} not found in {asset}")
    shutil.copy2(found, _bin_dir() / binary)
    try:
        (_bin_dir() / binary).chmod((_bin_dir() / binary).stat().st_mode | 0o111)
    except OSError:
        pass
    archive.unlink(missing_ok=True)


def install_tool(name: str, *, dry_run: bool = False) -> None:
    if name not in TOOLS:
        raise LabError(f"Unknown tool: {name}", hint="canfar-lab agent install --list")
    if dry_run:
        return
    resolve_session_env(ensure=True)
    _ensure_bin_dir()
    arch = platform.machine()

    if name == "node":
        _require("pixi")
        session = resolve_session_env(ensure=False)
        pixi_bin = session.pixi_home / "bin"
        bin_dir = _bin_dir()
        run(["pixi", "global", "install", "nodejs"], env=_session_environ())
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
    elif name == "opencode":
        env = {"XDG_BIN_DIR": str(_bin_dir())}
        _curl_pipe_bash("https://opencode.ai/install", env=env)
        opencode_src = _bin_dir() / "opencode"
        if not opencode_src.is_file():
            opencode_src = Path.home() / ".opencode" / "bin" / "opencode"
        _link_into_local_bin(opencode_src, "opencode")
        _verify_cmd("opencode", extra_paths=[opencode_src])
    elif name == "codex":
        _require("gh")
        run_capture(["gh", "auth", "status"])
        asset = f"codex-{arch}-unknown-linux-musl.tar.gz"
        if arch not in ("x86_64", "aarch64"):
            raise LabError(f"Unsupported architecture: {arch}")
        tmp = Path(_session_environ().get("TMPDIR", "/tmp"))
        run(
            ["gh", "release", "download", "-R", "openai/codex", "-p", asset, "-D", str(tmp)],
            env=_session_environ(),
        )
        with tarfile.open(tmp / asset, "r:gz") as tf:
            tf.extractall(_bin_dir())
        binary = asset.removesuffix(".tar.gz")
        src = _bin_dir() / binary
        if src.is_file():
            src.rename(_bin_dir() / "codex")
        try:
            (_bin_dir() / "codex").chmod((_bin_dir() / "codex").stat().st_mode | 0o111)
        except OSError:
            pass
        _verify_cmd("codex")
    elif name == "copilot":
        env = {"PREFIX": str(_npm_prefix()), "CI": "1"}
        _curl_pipe_bash("https://gh.io/copilot-install", env=env)
        copilot_bin = _npm_prefix() / "bin" / "copilot"
        _link_into_local_bin(copilot_bin, "copilot")
        _verify_cmd("copilot", extra_paths=[copilot_bin])
    elif name == "goose":
        env = {"GOOSE_BIN_DIR": str(_bin_dir()), "CONFIGURE": "false"}
        _curl_pipe_bash(
            "https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh",
            env=env,
        )
        _verify_cmd("goose")
    elif name == "kilo":
        env = {"XDG_BIN_DIR": str(_bin_dir())}
        try:
            _curl_pipe_bash("https://kilo.ai/cli/install", env=env)
        except subprocess.CalledProcessError:
            pass  # fall back to npm when upstream installer is unavailable
        if shutil.which("kilo") is None and not (_bin_dir() / "kilo").is_file():
            _require("npm")
            run(
                ["npm", "install", "-g", "--prefix", str(_npm_prefix()), "@kilocode/cli@latest"],
                env=_session_environ(),
            )
        _verify_cmd("kilo")
    elif name == "cline":
        _require("npm")
        run(
            ["npm", "install", "-g", "--prefix", str(_npm_prefix()), "cline@latest"],
            env=_session_environ(),
        )
        _verify_cmd("cline")
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
        )
        _verify_cmd(name if name != "pi" else "pi")
    elif name == "swival":
        _require("uv")
        run(["uv", "tool", "install", "--force", "swival"], env=_session_environ())
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
                ["gh", "release", "view", "-R", "sharkdp/hyperfine", "--json", "tagName"]
            )
            import json

            tag = json.loads(tag_raw).get("tagName", tag)
        except LabError:
            pass
        asset = f"hyperfine-{tag}-{arch}-unknown-linux-gnu.tar.gz"
        _gh_release_bin("sharkdp/hyperfine", asset, "hyperfine")
        _verify_cmd("hyperfine")
