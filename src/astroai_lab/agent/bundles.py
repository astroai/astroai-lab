"""Back-compat shim for the Phase 0 decomposition (docs/agent-rethink-plan.md).

The 995-line monolith was split into three focused modules with byte-identical
behavior:

- ``setup.py``     — config writing + setup orchestration
- ``upstream.py``  — GitHub upstream skill sync
- ``inventory.py`` — dir scans + config presence/syntax verification

This module re-exports every public (and a few internal) name so existing
imports keep working during the deprecation window. Prefer importing from the
new modules going forward.
"""

from __future__ import annotations

from astroai_lab.agent.inventory import (
    list_bundles,
    list_skills_inventory,
    verify_config_syntax,
    verify_setup,
)
from astroai_lab.agent.setup import (
    SetupResult,
    agent_list_bundles,
    agent_setup,
    agent_sync,
    agent_verify,
    default_bundle_names,
    ensure_agent_dirs,
    install_file,
    install_goose_config,
    install_tree,
    merge_claude_json,
    merge_mcp_servers,
    merge_opencode_mcp,
    run_bundle,
    write_stamp,
)
from astroai_lab.agent.upstream import (
    SourceUpdateResult,
    install_upstream_skill,
    install_upstream_skills,
    list_github_sources,
    update_all_github_sources,
    update_github_source,
    upstream_cache_path,
)

__all__ = [
    "SourceUpdateResult",
    "SetupResult",
    "agent_list_bundles",
    "agent_setup",
    "agent_sync",
    "agent_verify",
    "default_bundle_names",
    "ensure_agent_dirs",
    "install_file",
    "install_goose_config",
    "install_tree",
    "install_upstream_skill",
    "install_upstream_skills",
    "list_bundles",
    "list_github_sources",
    "list_skills_inventory",
    "merge_claude_json",
    "merge_mcp_servers",
    "merge_opencode_mcp",
    "run_bundle",
    "update_all_github_sources",
    "update_github_source",
    "verify_config_syntax",
    "verify_setup",
    "write_stamp",
    "upstream_cache_path",
]
