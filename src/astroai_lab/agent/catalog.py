"""Curated Catalog of AI coding agents, skills, rules, MCP servers, and container UIs.

Provides a unified directory of AI tools and session capabilities on AstroAI / CANFAR.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from astroai_lab.agent.addons import list_addons
from astroai_lab.agent.install import list_tools_status
from astroai_lab.agent.setup_state import read_setup_state


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    kind: str  # agent, skill, rule, mcp, tool, container
    tags: list[str]
    summary: str
    homepage: str
    installed: bool
    install_command: str
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Curated Container & Agent definitions
CATALOG_CONTAINERS = [
    {
        "id": "openresearch",
        "name": "OpenResearch (orx)",
        "kind": "container",
        "tags": ["agent", "ui", "science", "open"],
        "summary": "OpenResearch (orx) autoresearch dashboard for CANFAR sessions",
        "homepage": "https://github.com/alphaXiv/openresearch-cli",
        "install_command": "canfar create --name orx contributed images.canfar.net/astroai/openresearch:latest",
        "notes": "Proxied at / (port 5000) with Agent Hub at /astroai-agents/",
    },
    {
        "id": "openworker",
        "name": "OpenWorker UI",
        "kind": "container",
        "tags": ["agent", "ui", "open"],
        "summary": "OpenWorker browser UI + Python agent server for CANFAR (no Tauri)",
        "homepage": "https://github.com/andrewyng/openworker",
        "install_command": "canfar create --name openworker contributed images.canfar.net/astroai/openworker:latest",
        "notes": "Browser UI + local agent server running on port 5000",
    },
    {
        "id": "webterm",
        "name": "WebTerm Session",
        "kind": "container",
        "tags": ["ui", "terminal"],
        "summary": "Browser web terminal (ttyd) with full AstroAI toolchain",
        "homepage": "https://github.com/astroai/astroai-containers",
        "install_command": "canfar create --name webterm contributed images.canfar.net/astroai/webterm:latest",
        "notes": "Standard interactive terminal session",
    },
    {
        "id": "notebook",
        "name": "JupyterLab Session",
        "kind": "container",
        "tags": ["ui", "data", "science"],
        "summary": "JupyterLab environment pre-loaded with AstroAI agent extensions",
        "homepage": "https://github.com/astroai/astroai-containers",
        "install_command": "canfar create --name notebook contributed images.canfar.net/astroai/notebook:latest",
        "notes": "JupyterLab browser UI",
    },
    {
        "id": "vscode",
        "name": "Code-Server (VSCode)",
        "kind": "container",
        "tags": ["ui", "ide"],
        "summary": "Browser VSCode server with pre-configured AI extensions",
        "homepage": "https://github.com/astroai/astroai-containers",
        "install_command": "canfar create --name vscode contributed images.canfar.net/astroai/vscode:latest",
        "notes": "In-browser VSCode experience",
    },
    {
        "id": "ray-manager",
        "name": "Ray Cluster Manager",
        "kind": "container",
        "tags": ["container", "science", "data"],
        "summary": "Ray cluster head node + Jobs dashboard manager",
        "homepage": "https://github.com/astroai/astroai-containers",
        "install_command": "canfar create --name raymgr --cpu 2 --memory 8 contributed images.canfar.net/astroai/ray-manager:latest",
        "notes": "Ray Dashboard & Cluster Job submitter",
    },
]

CATALOG_AGENTS = [
    {
        "id": "kilo",
        "name": "Kilo CLI",
        "kind": "agent",
        "tags": ["agent", "cli", "open"],
        "summary": "Open-source CLI coding agent supporting OpenRouter & custom models",
        "homepage": "https://github.com/kilocode/kilo",
        "install_command": "astroai-lab agent install kilo",
        "notes": "Sign in with `kilo auth` or set OPENROUTER_API_KEY",
    },
    {
        "id": "goose",
        "name": "Goose Agent",
        "kind": "agent",
        "tags": ["agent", "cli", "open"],
        "summary": "Block's open-source autonomous AI developer CLI",
        "homepage": "https://github.com/block/goose",
        "install_command": "astroai-lab agent install goose",
        "notes": "Uses ~/.config/goose/config.yaml",
    },
    {
        "id": "cline",
        "name": "Cline CLI",
        "kind": "agent",
        "tags": ["agent", "cli"],
        "summary": "Autonomous coding agent CLI with tool use and safety checks",
        "homepage": "https://github.com/cline/cline",
        "install_command": "astroai-lab agent install cline",
        "notes": "Configured via astroai-lab agent models free",
    },
    {
        "id": "opencode",
        "name": "OpenCode Interpreter",
        "kind": "agent",
        "tags": ["agent", "cli", "open"],
        "summary": "Terminal AI coding assistant supporting local & cloud LLMs",
        "homepage": "https://github.com/sst/opencode",
        "install_command": "astroai-lab agent install opencode",
        "notes": "Configured via ~/.config/opencode/opencode.json",
    },
    {
        "id": "codex",
        "name": "Codex CLI",
        "kind": "agent",
        "tags": ["agent", "cli"],
        "summary": "Lightweight OpenAI Codex & OpenRouter coding assistant",
        "homepage": "https://github.com/openai/codex",
        "install_command": "astroai-lab agent install codex",
        "notes": "Configured via ~/.codex/config.toml",
    },
    {
        "id": "qoder",
        "name": "Qoder CLI (qodercli)",
        "kind": "agent",
        "tags": ["agent", "cli"],
        "summary": "Multi-file structural refactoring and code generation CLI",
        "homepage": "https://qoder.ai",
        "install_command": "astroai-lab agent install qoder",
        "notes": "Binary installed as qodercli on PATH",
    },
]


def list_agent_catalog(
    *,
    kind: str | None = None,
    tag: str | None = None,
    query: str | None = None,
    home: Path | None = None,
) -> list[dict[str, Any]]:
    """Build a unified Catalog of agents, skills, rules, MCP servers, and containers."""
    home = home or Path.home()
    items: list[dict[str, Any]] = []

    # 1. Add containers
    for c in CATALOG_CONTAINERS:
        items.append(
            {
                "id": c["id"],
                "name": c["name"],
                "kind": c["kind"],
                "tags": c["tags"],
                "summary": c["summary"],
                "homepage": c["homepage"],
                "installed": True,  # Available in CANFAR container ecosystem
                "install_command": c["install_command"],
                "notes": c["notes"],
            }
        )

    # 2. Add CLI agents
    tools_status = {t["name"]: t["installed"] for t in list_tools_status()}
    for a in CATALOG_AGENTS:
        is_installed = bool(tools_status.get(a["id"]))
        items.append(
            {
                "id": a["id"],
                "name": a["name"],
                "kind": a["kind"],
                "tags": a["tags"],
                "summary": a["summary"],
                "homepage": a["homepage"],
                "installed": is_installed,
                "install_command": a["install_command"],
                "notes": a["notes"],
            }
        )

    # 3. Add curated addons (skills, rules, MCPs, tools)
    addons = list_addons(home=home)
    for add in addons:
        kind_name = add["kind"]
        install_cmd = f"astroai-lab agent add {add['id']}"
        items.append(
            {
                "id": add["id"],
                "name": add["id"].replace("-", " ").title(),
                "kind": kind_name,
                "tags": add["tags"],
                "summary": add["summary"],
                "homepage": add["homepage"],
                "installed": add["installed"],
                "install_command": install_cmd,
                "notes": "Default addon" if add.get("default") else "",
            }
        )

    # Filtering
    filtered: list[dict[str, Any]] = []
    q = query.lower().strip() if query else None

    for item in items:
        if kind and item["kind"] != kind.lower():
            continue
        if tag and tag.lower() not in [t.lower() for t in item["tags"]]:
            continue
        if q:
            searchable = f"{item['id']} {item['name']} {item['summary']} {' '.join(item['tags'])}".lower()
            if q not in searchable:
                continue
        filtered.append(item)

    return filtered


# Backward compatibility alias
list_awesome_catalog = list_agent_catalog
