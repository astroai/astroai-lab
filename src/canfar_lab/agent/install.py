from __future__ import annotations

import os
import platform
import shutil
import subprocess
import tarfile
import zipfile
from pathlib import Path

from canfar_lab.errors import LabError
from canfar_lab.utils.subprocess import run, run_capture, which

BIN_DIR = Path.home() / ".local" / "bin"

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


def list_tools() -> dict[str, str]:
    return dict(TOOLS)


def _ensure_bin_dir() -> None:
    BIN_DIR.mkdir(parents=True, exist_ok=True)


def _curl_pipe_bash(url: str, *, env: dict[str, str] | None = None) -> None:
    _require("curl")
    merged = {**os.environ, **(env or {})}
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
    dst = BIN_DIR / name
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.symlink_to(src)


def _verify_cmd(cmd: str, *, extra_paths: list[Path] | None = None) -> None:
    if which(cmd) is not None:
        return
    candidates = [BIN_DIR / cmd, *(extra_paths or [])]
    for path in candidates:
        if path.is_file() and os.access(path, os.X_OK):
            return
    raise LabError(f"{cmd} not found on PATH after install — open a new shell")


def _require(cmd: str) -> None:
    if which(cmd) is None:
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
    shutil.copy2(found, BIN_DIR / binary)
    archive.unlink(missing_ok=True)


def install_tool(name: str, *, dry_run: bool = False) -> None:
    if name not in TOOLS:
        raise LabError(f"Unknown tool: {name}", hint="canfar-lab agent install --list")
    if dry_run:
        return
    _ensure_bin_dir()
    arch = platform.machine()

    if name == "node":
        _require("pixi")
        pixi_bin = Path(os.environ.get("PIXI_HOME", Path.home() / ".pixi")) / "bin"
        run(["pixi", "global", "install", "nodejs"])
        for cmd in ("node", "npm", "npx"):
            src = pixi_bin / cmd
            if src.is_file():
                (BIN_DIR / cmd).unlink(missing_ok=True)
                (BIN_DIR / cmd).symlink_to(src)
        _verify_cmd("node")
        _verify_cmd("npm")
    elif name == "agent":
        _curl_pipe_bash("https://cursor.com/install")
        _verify_cmd("agent")
    elif name == "claude":
        _curl_pipe_bash("https://claude.ai/install.sh")
        _verify_cmd("claude")
    elif name == "agy":
        _curl_pipe_bash("https://antigravity.google/cli/install.sh")
        _verify_cmd("agy")
    elif name == "opencode":
        env = {"XDG_BIN_DIR": str(BIN_DIR)}
        _curl_pipe_bash("https://opencode.ai/install", env=env)
        _link_into_local_bin(Path.home() / ".opencode" / "bin" / "opencode", "opencode")
        _verify_cmd("opencode", extra_paths=[Path.home() / ".opencode" / "bin" / "opencode"])
    elif name == "codex":
        _require("gh")
        run_capture(["gh", "auth", "status"])
        asset = f"codex-{arch}-unknown-linux-musl.tar.gz"
        if arch not in ("x86_64", "aarch64"):
            raise LabError(f"Unsupported architecture: {arch}")
        tmp = Path(os.environ.get("TMPDIR", "/tmp"))
        run(["gh", "release", "download", "-R", "openai/codex", "-p", asset, "-D", str(tmp)])
        with tarfile.open(tmp / asset, "r:gz") as tf:
            tf.extractall(BIN_DIR)
        binary = asset.removesuffix(".tar.gz")
        src = BIN_DIR / binary
        if src.is_file():
            src.rename(BIN_DIR / "codex")
        _verify_cmd("codex")
    elif name == "copilot":
        env = {"PREFIX": str(Path.home() / ".local")}
        _curl_pipe_bash("https://gh.io/copilot-install", env=env)
        _verify_cmd("copilot")
    elif name == "goose":
        env = {"GOOSE_BIN_DIR": str(BIN_DIR), "CONFIGURE": "false"}
        _curl_pipe_bash(
            "https://github.com/aaif-goose/goose/releases/download/stable/download_cli.sh",
            env=env,
        )
        _verify_cmd("goose")
    elif name == "kilo":
        env = {"XDG_BIN_DIR": str(BIN_DIR)}
        _curl_pipe_bash("https://kilo.ai/cli/install", env=env)
        if which("kilo") is None and not (BIN_DIR / "kilo").is_file():
            _require("npm")
            run(["npm", "install", "-g", "--prefix", str(Path.home() / ".local"), "@kilocode/cli"])
        _verify_cmd("kilo")
    elif name == "cline":
        _require("npm")
        run(["npm", "install", "-g", "--prefix", str(Path.home() / ".local"), "cline"])
        _verify_cmd("cline")
    elif name in ("freebuff", "pi", "codewhale"):
        _require("npm")
        pkg = {
            "freebuff": "freebuff",
            "pi": "@earendil-works/pi-coding-agent",
            "codewhale": "codewhale",
        }[name]
        run(["npm", "install", "-g", "--prefix", str(Path.home() / ".local"), pkg])
        _verify_cmd(name if name != "pi" else "pi")
    elif name == "swival":
        _require("uv")
        run(["uv", "tool", "install", "swival"])
        _verify_cmd("swival")
    elif name == "ast-grep":
        if arch not in ("x86_64", "aarch64"):
            raise LabError(f"Unsupported architecture: {arch}")
        asset = f"app-{arch}-unknown-linux-gnu.zip"
        _gh_release_bin("ast-grep/ast-grep", asset, "sg")
        (BIN_DIR / "ast-grep").unlink(missing_ok=True)
        (BIN_DIR / "ast-grep").symlink_to(BIN_DIR / "sg")
        _verify_cmd("sg")
    elif name == "hyperfine":
        if which("hyperfine"):
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
