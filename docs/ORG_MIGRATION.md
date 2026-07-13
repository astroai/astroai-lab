# Org migration & CANFAR adoption notes

This is a **checklist**, not an automated transfer. Performing GitHub org moves
requires human credentials and confirmations.

## Current local names

| Local path | Intended GitHub | Former |
|------------|-----------------|--------|
| `~/src/astroai-lab` | `astroai/astroai-lab` (or `sfabbro/astroai-lab` until org exists) | `canfar-lab` |
| `~/src/astroai-containers` | `astroai/astroai-containers` | `containers` |
| `~/src/astroai-workload` | `astroai/astroai-workload` | unchanged |

Harbor images stay `images.canfar.net/astroai/*` regardless of GitHub org.

## GitHub rename / transfer steps (human)

1. Create or use the `astroai` GitHub organization.
2. For each repo: **Settings → Rename** (or Transfer to `astroai`), preserving redirects.
3. Update `pyproject.toml` / README URLs (already point at `astroai-lab`).
4. Update image build CI secrets if remotes change.
5. Announce the hard rename: CLI is `astroai-lab` only (no `canfar-lab` alias).

Suggested `gh` sequence once ready:

```bash
# Example only — run by a human with org admin rights
gh repo rename astroai-lab --repo sfabbro/canfar-lab
gh api -X POST repos/sfabbro/astroai-lab/transfer -f new_owner=astroai
# containers already under astroai/astroai-containers (optional rename to astroai-containers)
gh api -X POST repos/sfabbro/astroai-workload/transfer -f new_owner=astroai
```

## CANFAR adoption packet (optional)

If CANFAR staff want to adopt AstroAI session images later:

- Images: already published under Harbor project `astroai`.
- Docs: point users at `astroai-lab guide` + storage tiers (`/scratch`, `/arc`, `vos:`).
- No OpenCADC `canfar` / `science-platform` code changes are required for this stack.
- Ray: stock Dashboard + headless workers; custom manager UI is frozen.

## Explicit non-goals for this packet

- Forking or patching `opencadc/canfar` / `opencadc/science-platform`.
- Keeping a forever `canfar-lab` CLI alias.
- Building a long-term custom Ray web console.

## Current remotes (local)

- `astroai-lab` origin may still be `sfabbro/canfar-lab` until GitHub rename.
- `astroai-containers` origin may already be `astroai/astroai-containers`.
