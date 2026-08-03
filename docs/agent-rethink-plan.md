# astroai-agent rethink: prune, unify, plugin-ify

Status: **in progress** — Phases 0–3 landed (prune + decompose, agent
registry, lean verbs, plugin system) plus the Phase 2 `setup <agent>` /
`config <agent>` / `update <agent>` / `fix-config <agent>` registry-driven
verbs. Phases 4–5 remain.
Owner: astroai-lab.
Companion docs: [cli.md](cli.md), [USAGE.md](USAGE.md), [help.md](help.md).

---

## 1. Why

`astroai-lab agent` grew organically to **16 verbs** (14 commands + the
`skills`/`models` sub-typers) across **10 modules (~3,050 lines)**. The surface overlaps (skills vs addons vs bundles; report vs status vs
interact), the largest module (`bundles.py`, 995 lines) mixes setup, upstream
sync, and inventory concerns, and everything is hand-maintained per agent rather
than driven by a registry.

The goals:

1. **Lean interface** — a canonical verb set users can memorize: `list`,
   `catalog`, `install`, `remove`, `setup`, `config`, `fix-config`, `update`,
   `status`, `verify`, `plugins`.
2. **Single source of truth** — an agent registry (data, not code) drives every
   verb; adding an agent is a one-line YAML entry, not a code branch.
3. **Plugin system** — one uniform surface to install/update/remove/configure
   **skills, MCP servers, config snippets, and addons** across *all* installed
   agents. The legacy `addons.json` catalog was migrated into
   `plugins/*.yaml` (Phase 3), making the plugin registry the initial catalog.
4. **New agents onboarded properly** — `hermes` (Nous Research) and `openclaw`
   (openclaw/openclaw) get full registry entries (install/setup/config/verify +
   plugin support), and the Ray-on-CANFAR story is exposed to them as a skill
   (`canfar-ray`, already added) and as MCP tools (`ray-manager-mcp`, shipped
   in Phase 3).

---

## 2. Current state (inventory)

### 2.1 Verb surface (`src/astroai_lab/cli/agent_cmd.py`)

| Verb | Kind | Notes |
|------|------|-------|
| `catalog` | read | curated agents + skills + MCPs + container UIs |
| `list` | read | tools + bundles + skills overview |
| `install` | write | download a CLI binary (kilo, opencode, qoder, hermes, openclaw, …) |
| `setup` | write | MCP/rules/skills configs (`--list` for bundles) |
| `update` | write | refresh state / upstream skills |
| `addons` | read | curated lean + science addons |
| `add` | write | install curated addon(s) by id or `--tag` |
| `skills list/update` | mixed | Cursor skill inventory / upstream refresh |
| `project` | write | per-project scaffold |
| `status` | read | binaries + configs at a glance |
| `verify` | read/fix | presence + config syntax checks (`--fix`) |
| `fix` | write | auto-repair setup state, locks, config syntax |
| `clean` | write | remove stale locks, failed markers, empty configs |
| `interact` | read | active container UI endpoints + agent CLI status |
| `report` | read | one-shot JSON health (wizard) |
| `models` | mixed | free-tier model presets (OpenRouter / Kilo) |

Top-level count: 14 `@agent_app.command` verbs + the `skills` and `models`
sub-typers = 16 entries.

### 2.2 Modules (`src/astroai_lab/agent/`)

Post-Phase-0/1 layout (as of this document):

| Module | Role |
|--------|------|
| `registry.py` | **agent registry**: load/validate `agents/*.yaml`, status, install/remove dispatch |
| `install.py` | CLI binary download (curl / npm / gh-release) + `TOOLS` (non-agent utilities) |
| `setup.py` | config writing (extracted from `bundles.py`) |
| `upstream.py` | github-skill sync (extracted from `bundles.py`) |
| `inventory.py` | dir scans + config syntax/presence verification (extracted from `bundles.py`) |
| `addons.py` | curated addons: bundled/github-skill/github-bundle/github-rule/mcp-snippet/cli-tool/**agent-skill** |
| `free_models.py` | free-tier model presets |
| `catalog.py` | catalog assembly + filtering (registry-driven agent rows) |
| `setup_state.py` | install state / stamps / timeouts |
| `fix.py` | auto-repair |
| `interact.py` | endpoint/status inspection |
| `clean_agent.py` | stale-state cleanup |
| `bundle_path.py` | bundle root resolution |

Overlap: `addons.py` ↔ `catalog.py` (both list curated content), `skills` (in
`agent_cmd.py`) vs `addons.py` (both manage skills), `report` vs `status` vs
`interact` (three ways to ask "what's going on").

---

## 3. Target interface

```
astroai-lab agent
  list                        # installed agents + plugin coverage
  catalog                     # curated agents / skills / MCPs / containers (registry-driven)
  install <agent>             # registry-driven (CLI download + binary link)
  remove <agent>              # NEW: uninstall CLI + configs + state
  setup <agent>               # write configs/skills/MCP for one agent (or all)
  config <agent> [key=val]    # show/edit an agent's config file (NEW surface)
  fix-config <agent>          # repair syntax / regenerate (from verify --fix)
  update <agent>              # refresh CLI + upstream skills + state
  status                      # binaries + configs + plugins at a glance
  verify [--fix]              # presence + syntax checks
  models                      # free-tier model presets (kept as-is)
  plugins
    list [--agent A]          # installed + available plugins (skill/mcp/config/addon)
    install <plugin-id> [--agent A]   # apply to all agents that support it by default
    update <plugin-id>
    remove <plugin-id>
    configure <plugin-id>     # per-agent config merge (e.g. MCP server entry)
```

**Merges:**

| Old verb | → | Target |
|----------|---|--------|
| `addons` | → | `plugins list --kind addon` (alias kept for one release) |
| `add` | → | `plugins install` |
| `skills list/update` | → | `plugins list/update --kind skill` |
| `project` | → | `config --scope project` (kept as thin alias) |
| `report` | → | `status --json` |
| `interact` | → | `status --endpoints` |
| `clean` | → | `fix --clean` |
| `fix` | → | `fix-config --all` + `verify --fix` |
| `models` | → | **kept as-is** (distinct concern; `--json` stays) |

Aliases from the old names are kept for one deprecation window, then removed.

Note on `interact`: it is the only surface that lists **active container UI
endpoints** (the wizard depends on it). `status --endpoints` must preserve that
surface verbatim — the merge is a rename, not a cut. `models` stays a top-level
verb (its free-tier preset logic is unrelated to plugin management).

---

## 4. Phase plan

### Phase 0 — Audit & prune

- [x] Map every old verb to the target surface (table above); deprecated aliases
      (`fix`, `clean`, `report`, `interact`) emit a hint pointing at the new verb.
- [x] Decompose `bundles.py` (995 lines) into `setup.py` (config writing),
      `upstream.py` (github-skill sync), and `inventory.py` (dir scans) —
      byte-identical behavior, unit tests added as the split happened.
- [x] Add a `cli_contract_test` (`tests/cli/test_cli_agent_contract.py`) that pins
      the verb list + one-line help (golden test, fails on surface growth).
- [x] Update `docs/cli.md`, `docs/USAGE.md`, `docs/help.md` to the new surface.

### Phase 1 — Agent registry (single source of truth)

- [x] `agent/registry.py` + `data/agent/agents/*.yaml` — one file per agent:

      ```yaml
      id: openclaw
      name: OpenClaw
      homepage: https://github.com/openclaw/openclaw
      binary: openclaw
      install:
        method: npm            # npm | curl | gh-release | uv-tool
        source: openclaw@latest
        requires_node: ">=24.15"   # baked Node 24.18.1 in base image
      config:
        path: ~/.openclaw/openclaw.json
        format: json5
        provider_key: OPENROUTER_API_KEY
      setup:
        post_install: openclaw onboard    # interactive; skipped in containers
      verify:
        - "openclaw --version"
        - "test -f ~/.openclaw/openclaw.json"
      plugins: [skill, mcp, config, addon]
      ```

- [x] Registry loader with schema validation; `list`/`catalog`/`install`/`remove`/`verify`
      read from the registry instead of hard-coded branches.
- [x] `agent list` renders installed status from the registry + `tool_on_path`.
- [x] Migrated `kilo`, `goose`, `cline`, `opencode`, `codex` out of
      `install.TOOLS` into `agents/*.yaml` (hermes/openclaw joined earlier);
      TOOLS now only holds the non-registry utilities (node, claude, copilot…)
      plus hermes/openclaw, which keep their battle-tested installers there and
      are mirrored in the registry for status/verify/remove.

**The registry is the single source of truth.** Every agent lives as one YAML
file under `src/astroai_lab/data/agent/agents/<id>.yaml` (schema above); the
loader validates on read and fails loudly on a bad entry. `install.TOOLS`
remains only for utilities that are *not* agents (`node`, `claude`, `copilot`,
`qoder`, `hermes`, `openclaw` keep their battle-tested installers there and are
mirrored in the registry for status/verify/remove). Install dispatch:

| Agent | `install.method` | Installer behavior |
|-------|------------------|--------------------|
| `kilo`, `opencode` | `curl` | `curl \| bash` with `XDG_BIN_DIR={bin_dir}` env; `post_binary_paths` + `~/.<id>/bin` fallback |
| `goose` | `curl` | same, with `GOOSE_BIN_DIR={bin_dir}` + `CONFIGURE=false` |
| `cline` | `npm` | `npm install -g --prefix <npm_prefix> cline@latest` |
| `codex` | `gh-release` | `gh release download` with `{arch}` templating → `platform.machine()` |
| `hermes`, `openclaw` | (TOOLS) | legacy `install_tool` branches; registry mirrors status/config/verify |

`agent list`/`agent catalog`/`agent verify` read binary+config status from the
registry (`registry_agent_status` → `tool_on_path` + `config.path` presence);
`agent install <id>` dispatches on `install.method`; `agent remove <id>`
uninstalls per method and drops config/plugin files. Adding a new agent is one
YAML file — no Python branch required.

**Installs never target `~/.local`.** The session bin dir is
`$ASTROAI_LAB_BIN_DIR` → scratch `.local/bin` → team project `.local/bin` →
runtime root `work/.runtime-$USER/bin` (last resort). The user-home fallback
was removed so package installs never pollute `~/.local`; config files still
live in home dirs (e.g. `~/.hermes/config.yaml`) — that's the supported split.

### Phase 2 — Lean agent verbs

- [x] `install <agent>` — registry-driven; dispatches on `install.method` and
      reuses the existing `install.py` helpers (`_curl_pipe_bash`, npm
      `--prefix`, `_gh_release_bin`, `uv tool install`).
- [x] `remove <agent>` (**new**) — uninstall binary + remove config files +
      clear `setup_state` stamps + drop plugin-created files. `--purge` also
      removes `~/.hermes`, `~/.openclaw`, etc. dry-run supported (verified in
      container E2E: `agent remove hermes --purge`).
- [x] `setup <agent>` — registry-driven config writing (config scaffold +
      skills dir + plugin re-apply) for a single agent, or `--all` for every
      installed agent (`registry.setup_registry_agent`). `--post-install` runs
      the interactive setup step (e.g. `openclaw onboard`) — opt-in.
- [x] `config <agent>` — show the agent's config file (or a `--key` value);
      `config <agent> key=value` writes a validated edit (JSON5-aware:
      comment-tolerant parse + textual targeted edits, so JSONC/JSON5 comments
      and trailing commas survive). YAML round-trips via `safe_dump`; TOML
      edits are line-based scalars; markdown is read-only (`agent/agent_config.py`).
- [x] `fix-config <agent>` — regenerate/sanitize the agent's config from the
      registry (missing → format-aware scaffold; broken → reset to a minimal
      valid body; markdown read-only), `--all` covers every installed agent;
      reuses `fix.py`'s repair pattern via `agent_config.validate_config_text`
      (`registry.fix_registry_agent`); `verify --fix` remains the broad sweep.
      Also fixed the jsonc/json5 scaffold to use `//` headers (JSONC/JSON5 do
      not support `#` comments), so a scaffolded config always parses back.
- [x] `update <agent>` — registry-driven: refresh CLI when missing (or always
      with `--reinstall`), force re-apply the agent's plugins, refresh state
      (`registry.update_registry_agent`).

### Phase 3 — Plugin system (the centerpiece)

- [x] `agent/plugins.py` + `data/agent/plugins/*.yaml` (one YAML per plugin,
      schema-validated loader like the agent registry):

      ```yaml
      id: canfar-ray
      kind: skill                    # skill | mcp | config | addon
      tags: [science, ray, canfar]
      summary: Drive CANFAR Ray clusters (ensure/status/scale/dashboard)
      agents: [hermes, openclaw]     # support matrix
      install:
        source: canfar-ray           # skill: bundled dir under skills/<source>
        targets:
          hermes: .hermes/skills/canfar-ray
          openclaw: .openclaw/skills/canfar-ray
      ```

- [x] `plugins install <id>` applies to **all installed agents** that declare
      support; `--agent` scopes it. `plugins update` (force re-apply) /
      `plugins remove` / `plugins configure` symmetric.
- [x] Seed catalog: migrate existing `addons.json` entries into the plugin
      registry (all 31 addons now live as `plugins/*.yaml` with `addon: true` +
      their `install.type` transport; `addons.json` is deleted). `addons.py` is
      now a shim over the plugin registry — `agent addons`/`agent add` and
      `agent plugins install` route through the same `_apply_addon` dispatcher.
- [x] `configure <plugin-id>` for `kind: mcp` merges an `mcpServers` entry into
      each agent's config (Cursor/Copilot/Claude/OpenCode + hermes YAML +
      openclaw JSON5). **Dynamic URLs only** (e.g.
      `$ASTROAI_RAY_JOBS_ADDRESS`) — never a hardcoded manager URL, since it
      differs per session.
- [x] **`ray-manager-mcp` ships as the `kind: mcp` example** (agents
      cursor/hermes/openclaw): `plugins configure ray-manager-mcp` wires
      `command: astroai-workload, args: [mcp, serve]` with a dynamic
      `$ASTROAI_RAY_JOBS_ADDRESS` env ref into each agent's config. Backed by
      the zero-dependency stdio MCP server in astroai-workload (`mcp serve`,
      tools: cluster_ensure / cluster_status / cluster_scale / dashboard_url).
- [x] Removal is recursive: `agent remove <agent>` removes its plugin-applied
      files via `plugins.remove_agent_plugin_files` (wired into the registry).

### Phase 4 — hermes + openclaw

In the catalog and the registry (`agent install hermes|openclaw`, verified
`:26.08` Node 24.18.1; container E2E proved install → status → verify → remove
for hermes). Registry entries landed in Phase 1 with full install/setup/config/verify.
Specifics:

- **hermes** (Nous Research): curl installer `https://hermes-agent.nousresearch.com/install.sh`;
  config `~/.hermes/config.yaml` (+ `~/.hermes/.env` secrets); OpenRouter
  first-class; skills at `~/.hermes/skills/`; headless `hermes -z "task"`.
  *Caveat:* install URL is web-researched — verify against the repo README.
- **openclaw**: `npm install -g openclaw@latest` (Node 24.18.1 baked ✅); config
  `~/.openclaw/openclaw.json` (JSON5); skills at `~/.openclaw/skills/` +
  ClawHub `openclaw skills install @owner/slug`; headless
  `openclaw agent --message "…"`.
- Both get `canfar-ray` plugin coverage (already wired via the `agent-skill`
  install type) and the `ray-manager-mcp` `kind: mcp` plugin entry (shipped in
  Phase 3): `astroai-workload mcp serve` exposes the Ray cluster tools
  (ensure/status/scale/dashboard) over stdio, wired with a dynamic
  `$ASTROAI_RAY_JOBS_ADDRESS` env ref (resolved per-session, never hardcoded).
  Container E2E proved the entry lands in `~/.hermes/config.yaml` +
  `~/.openclaw/openclaw.json` (+ `~/.cursor/mcp.json`) for both agents.

### Phase 5 — Tests, docs, CI

- [x] Registry loader + schema tests, `agent install`/`remove` unit tests, and the
      golden CLI-contract test (full suite green at 75%+ coverage).
- [x] Plugin system tests: `tests/unit/test_plugins.py` (loader/schema, status,
      install/update/remove/configure for skill/mcp/config, recursive removal,
      CLI surface) + contract test pins the `plugins` verb.
- [x] Unit tests per remaining verb (setup/config/fix-config/update).
- [x] `scripts/canfar-verify-agents.sh` updated to the new verb surface
      (`agent plugins list`, `agent fix-config --all`, `agent status
      --endpoints`; deprecated `fix`/`clean`/`interact` aliases dropped from
      the smoke), plus a post-install `fix-config --all` + `agent config kilo`
      pass that exercises the registry verbs against the freshly installed
      agents.
- [x] `docs/cli.md` / `docs/USAGE.md` document the registry as source of truth
      (this doc too).
- [ ] Deprecation shims emit a hint pointing at the new verb, then are removed.

---

## 5. Acceptance criteria

- `astroai-lab agent --help` fits on one screen with ≤ 11 verbs (+ `plugins`).
- Adding an agent = adding one YAML file; no Python branch needed.
- `agent remove <agent>` leaves no trace (binary, configs, stamps, plugins).
- `agent plugins install canfar-ray` puts the SKILL.md into every installed
  agent that supports skills, and `plugins remove` deletes it.
- Full unit suite + coverage gate (75%) stay green at every phase.
- hermes and openclaw appear in `catalog`, install cleanly, and can
  `cluster ensure/status/scale/dashboard` on CANFAR via the `canfar-ray` skill.

## 6. Risks / open questions

- **Back-compat:** one deprecation window with aliases; `canfar-verify-agents.sh`
  and docs must move in the same release.
- **Registry schema churn:** lock the schema with validation from day one.
- **hermes installer URL** unverified (web research); verify before Phase 4 ships.
- **openclaw `onboard`** is interactive (daemon install) — keep it opt-in in
  containers; document for interactive sessions.
- **Dynamic manager URL** for the MCP plugin — resolve at session time
  (`$ASTROAI_RAY_JOBS_ADDRESS`), never bake a per-session URL into configs.
