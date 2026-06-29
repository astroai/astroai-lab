"""Free-tier model presets for open coding agents.

Community patterns (2026):
- Kilo: kilo-auto/free — sign in at kilo.ai, no API key to start ($20 trial credits).
- OpenRouter :free models — key at openrouter.ai/keys, no credit card; 50 req/day
  (1000/day after $10 credit). Best free coding: qwen/qwen3-coder:free (262K ctx).
- Goose / OpenCode / Codex / Cline: point at OpenRouter with OPENROUTER_API_KEY.
"""

from __future__ import annotations

import json
import os
import subprocess
import shutil
from pathlib import Path
from typing import Any

from canfar_lab.agent.bundle_path import bundle_root
from canfar_lab.errors import LabError


OPENROUTER_KEY_ENV = "OPENROUTER_API_KEY"
OPENROUTER_DOCS = "https://openrouter.ai/docs/guides/routing/provider-selection#free-model-routing"

# OpenRouter :free suffix — no payment required for the key itself.
PRESETS: dict[str, dict[str, str]] = {
    "coding": {
        "label": "Best free coding (262K context)",
        "openrouter": "qwen/qwen3-coder:free",
        "kilo": "kilo-auto/free",
        "description": "Qwen3 Coder on OpenRouter free tier; strong tool use for agents.",
    },
    "long": {
        "label": "Long context (1M tokens)",
        "openrouter": "google/gemini-2.0-flash-lite:free",
        "kilo": "kilo-auto/free",
        "description": "Gemini Flash Lite free tier for large repos and docs.",
    },
    "reasoning": {
        "label": "Reasoning / planning",
        "openrouter": "deepseek/deepseek-r1:free",
        "kilo": "kilo-auto/efficient",
        "description": "DeepSeek R1 free tier for multi-step reasoning.",
    },
}

DEFAULT_PRESET = "coding"


def list_presets() -> dict[str, dict[str, str]]:
    return dict(PRESETS)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _merge_dicts(out[key], val)
        else:
            out[key] = val
    return out


def _openrouter_model(model: str) -> str:
    return model if model.startswith("openrouter/") else f"openrouter/{model}"


def _openrouter_key() -> str | None:
    return os.environ.get(OPENROUTER_KEY_ENV) or os.environ.get("OPENROUTER_KEY")


def _template(name: str) -> Path:
    path = bundle_root() / "free-models" / name
    if not path.is_file():
        raise LabError(f"Missing free-models template: {name}")
    return path


def apply_kilo(home: Path, preset: str, *, force: bool, dry_run: bool) -> bool:
    cfg = home / ".config" / "kilo" / "kilo.jsonc"
    if cfg.is_file() and not force:
        return False
    if dry_run:
        return True
    data = _read_json(_template("kilo.jsonc"))
    data["model"] = PRESETS[preset]["kilo"]
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return True


def apply_goose(home: Path, preset: str, *, force: bool, dry_run: bool) -> bool:
    cfg = home / ".config" / "goose" / "config.yaml"
    model = PRESETS[preset]["openrouter"]
    block = (
        "# CANFAR lab free models — set OPENROUTER_API_KEY (openrouter.ai/keys)\n"
        f"GOOSE_PROVIDER: openrouter\n"
        f"GOOSE_MODEL: {model}\n"
    )
    if cfg.is_file() and not force:
        text = cfg.read_text(encoding="utf-8")
        if "GOOSE_PROVIDER:" in text and "GOOSE_MODEL:" in text:
            return False
        block = text.rstrip() + "\n\n" + block
    elif cfg.is_file():
        block = cfg.read_text(encoding="utf-8").rstrip() + "\n\n" + block
    if dry_run:
        return True
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(block, encoding="utf-8")
    return True


def apply_opencode(home: Path, preset: str, *, force: bool, dry_run: bool) -> bool:
    cfg = home / ".config" / "opencode" / "opencode.json"
    model = _openrouter_model(PRESETS[preset]["openrouter"])
    small = _openrouter_model(PRESETS["long"]["openrouter"])
    overlay = {"model": model, "small_model": small}
    if not cfg.is_file() or force:
        base: dict[str, Any] = {}
        if cfg.is_file():
            base = _read_json(cfg)
        merged = _merge_dicts(base, overlay)
        if dry_run:
            return True
        _write_json(cfg, merged)
        return True
    data = _read_json(cfg)
    if data.get("model") == model and not force:
        return False
    if dry_run:
        return True
    _write_json(cfg, _merge_dicts(data, overlay))
    return True


def apply_codex(home: Path, preset: str, *, force: bool, dry_run: bool) -> bool:
    cfg = home / ".codex" / "config.toml"
    model = PRESETS[preset]["openrouter"]
    snippet = (
        "\n# CANFAR lab free models (OpenRouter)\n"
        f'model = "{model}"\n'
        'model_provider = "openrouter"\n\n'
        "[model_providers.openrouter]\n"
        'name = "OpenRouter"\n'
        'base_url = "https://openrouter.ai/api/v1"\n'
        f'env_key = "{OPENROUTER_KEY_ENV}"\n'
    )
    if cfg.is_file() and not force:
        text = cfg.read_text(encoding="utf-8")
        if 'model_provider = "openrouter"' in text:
            return False
        snippet = text.rstrip() + "\n" + snippet
    elif cfg.is_file():
        snippet = cfg.read_text(encoding="utf-8").rstrip() + "\n" + snippet
    else:
        snippet = snippet.lstrip("\n")
    if dry_run:
        return True
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(snippet, encoding="utf-8")
    return True


def apply_cline(preset: str, *, dry_run: bool) -> str | None:
    if shutil.which("cline") is None:
        return "cline not installed — run: canfar-lab agent install cline"
    key = _openrouter_key()
    if not key:
        return (
            f"{OPENROUTER_KEY_ENV} not set — run: canfar-lab agent models free after exporting key"
        )
    model = PRESETS[preset]["openrouter"]
    if dry_run:
        return f"dry-run: cline auth -p openrouter -m {model}"
    proc = subprocess.run(
        ["cline", "auth", "-p", "openrouter", "-k", key, "-m", model],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return f"cline auth failed: {proc.stderr.strip() or proc.stdout.strip()}"
    return None


def write_openrouter_env(home: Path, *, dry_run: bool) -> bool:
    dst = home / ".config" / "canfar" / "lab" / "openrouter.env"
    example = home / ".config" / "canfar" / "lab" / "openrouter.env.example"
    if dry_run:
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    example.write_text(
        "# Free OpenRouter key — https://openrouter.ai/keys (no credit card)\n"
        f"# export {OPENROUTER_KEY_ENV}=sk-or-v1-...\n",
        encoding="utf-8",
    )
    key = _openrouter_key()
    if key and (not dst.is_file() or dst.read_text(encoding="utf-8").strip() == ""):
        dst.write_text(f'export {OPENROUTER_KEY_ENV}="{key}"\n', encoding="utf-8")
        return True
    return False


def ensure_openrouter_in_agent_env(home: Path, *, dry_run: bool) -> None:
    hook = home / ".config" / "canfar" / "lab" / "agent-env.sh"
    marker = "# canfar-lab openrouter"
    line = (
        f"{marker}\n"
        '[[ -f "${HOME}/.config/canfar/lab/openrouter.env" ]] '
        '&& source "${HOME}/.config/canfar/lab/openrouter.env"\n'
    )
    if dry_run:
        return
    hook.parent.mkdir(parents=True, exist_ok=True)
    if hook.is_file():
        text = hook.read_text(encoding="utf-8")
        if marker in text:
            return
        hook.write_text(text.rstrip() + "\n\n" + line, encoding="utf-8")
    else:
        hook.write_text(
            "# CANFAR lab agent setup — GitHub token for gh + GitHub MCP\n"
            "if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then\n"
            '  export GITHUB_TOKEN="$(gh auth token 2>/dev/null || true)"\n'
            "fi\n\n" + line,
            encoding="utf-8",
        )


def apply_free_models(
    home: Path | None = None,
    *,
    preset: str = DEFAULT_PRESET,
    force: bool = False,
    dry_run: bool = False,
    skip_cline: bool = False,
) -> list[str]:
    if preset not in PRESETS:
        raise LabError(
            f"Unknown preset: {preset}",
            hint="canfar-lab agent models --list",
        )
    home = home or Path.home()
    actions: list[str] = []
    info = PRESETS[preset]

    if apply_kilo(home, preset, force=force, dry_run=dry_run):
        actions.append(f"kilo → {info['kilo']} (~/.config/kilo/kilo.jsonc)")
    if apply_goose(home, preset, force=force, dry_run=dry_run):
        actions.append(f"goose → openrouter/{info['openrouter']}")
    if apply_opencode(home, preset, force=force, dry_run=dry_run):
        actions.append(f"opencode → openrouter/{info['openrouter']}")
    if apply_codex(home, preset, force=force, dry_run=dry_run):
        actions.append(f"codex → {info['openrouter']}")
    if write_openrouter_env(home, dry_run=dry_run):
        actions.append("openrouter.env written (~/.config/canfar/lab/)")
    ensure_openrouter_in_agent_env(home, dry_run=dry_run)

    if not skip_cline:
        cline_note = apply_cline(preset, dry_run=dry_run)
        if cline_note and cline_note.startswith("dry-run:"):
            actions.append(cline_note)
        elif cline_note is None and shutil.which("cline"):
            actions.append(f"cline → openrouter/{info['openrouter']}")
        elif cline_note:
            actions.append(f"cline: {cline_note}")

    if not actions and not dry_run:
        actions.append("configs already present (use --force to overwrite)")

    return actions


def free_models_guide() -> str:
    lines = [
        "Free frontier models for open coding agents",
        "===========================================",
        "",
        "Tier 1 — no API key (sign in):",
        "  kilo     kilo-auto/free     canfar-lab agent install kilo && kilo auth",
        "           Docs: https://kilo.ai/docs/code-with-ai/agents/model-selection",
        "",
        "Tier 2 — OpenRouter free (key at openrouter.ai/keys, no credit card):",
        f"  export {OPENROUTER_KEY_ENV}=sk-or-v1-...",
        "  canfar-lab agent models free",
        "  Limits: 20 req/min, 50/day (1000/day after $10 credit)",
        f"  Docs: {OPENROUTER_DOCS}",
        "",
        "Presets (canfar-lab agent models free --preset NAME):",
    ]
    for name, meta in PRESETS.items():
        lines.append(f"  {name:<10} {meta['label']}")
        lines.append(f"             OpenRouter: {meta['openrouter']}")
        lines.append(f"             Kilo:       {meta['kilo']}")
    lines.extend(
        [
            "",
            "Per-agent after setup:",
            "  goose      goose configure   # or use written GOOSE_* in config.yaml",
            "  opencode   opencode          # /connect OpenRouter if auth needed",
            "  codex      codex             # uses OPENROUTER_API_KEY",
            "  cline      cline auth        # or auto via models free",
            "  kilo       kilo              # /connect or kilo auth",
            "",
            "Paid subscriptions (bring your own): Cursor Agent, Claude Code, Copilot, Codex OAuth.",
        ]
    )
    return "\n".join(lines)
