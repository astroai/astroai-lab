"""Detect package caches that wrongly land under $HOME when /scratch is available."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Env vars that must not resolve under $HOME when scratch is writable.
CACHE_ENV_VARS = (
    "UV_CACHE_DIR",
    "PIXI_CACHE_DIR",
    "PIP_CACHE_DIR",
    "NPM_CONFIG_CACHE",
    "HF_HOME",
    "TORCH_HOME",
    "TRANSFORMERS_CACHE",
    "CONDA_PKGS_DIRS",
    "MAMBA_PKGS_DIRS",
    "XDG_CACHE_HOME",
    "TMPDIR",
)

# Relative paths under $HOME that should not accumulate when scratch exists.
HOME_CACHE_RELS = (
    ".cache/pip",
    ".cache/uv",
    ".cache/npm",
    ".cache/pixi",
    ".cache/conda",
    ".cache/huggingface",
    ".cache/torch",
    ".cache/matplotlib",
    ".local/share/pip",
    ".local/share/uv",
    ".conda",
    "mamba",
)


@dataclass(frozen=True)
class HygieneIssue:
    kind: str  # "env" | "path"
    detail: str


def _under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def check_home_cache_hygiene(
    *,
    home: Path | None = None,
    scratch: Path | None = None,
    env: dict[str, str] | None = None,
) -> list[HygieneIssue]:
    """Fail when scratch is usable but caches still point at / live under $HOME."""
    home = home or Path.home()
    environ = env if env is not None else dict(os.environ)
    issues: list[HygieneIssue] = []

    if scratch is None:
        raw = environ.get("TMP_SCRATCH_DIR", "").strip()
        scratch = Path(raw) if raw else Path("/scratch")
    if not scratch.is_dir() or not os.access(scratch, os.W_OK):
        return issues

    for var in CACHE_ENV_VARS:
        raw = environ.get(var, "").strip()
        if not raw:
            # Missing redirect is itself a problem for critical caches when scratch exists.
            if var in {"UV_CACHE_DIR", "PIXI_CACHE_DIR", "PIP_CACHE_DIR", "XDG_CACHE_HOME"}:
                issues.append(
                    HygieneIssue(
                        "env",
                        f"{var} unset while /scratch is writable — "
                        'run: eval "$(astroai-lab env export)"',
                    )
                )
            continue
        path = Path(raw)
        if _under(path, home) and not _under(path, scratch):
            issues.append(
                HygieneIssue(
                    "env",
                    f"{var}={raw} is under $HOME; should be under /scratch",
                )
            )

    for rel in HOME_CACHE_RELS:
        path = home / rel
        if path.exists():
            issues.append(
                HygieneIssue(
                    "path",
                    f"{path} exists on $HOME — run: astroai-lab clean home --all-safe --yes",
                )
            )
    return issues


def hygiene_ok(
    *,
    home: Path | None = None,
    scratch: Path | None = None,
    env: dict[str, str] | None = None,
) -> bool:
    return not check_home_cache_hygiene(home=home, scratch=scratch, env=env)
