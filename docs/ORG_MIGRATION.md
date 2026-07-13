# Org migration & CANFAR adoption notes

GitHub transfers for the AstroAI session stack are **done**. Harbor images stay
`images.canfar.net/astroai/*` regardless of GitHub org.

## Current names

| Local path | GitHub | Former |
|------------|--------|--------|
| `~/src/astroai-lab` | [`astroai/astroai-lab`](https://github.com/astroai/astroai-lab) | `sfabbro/canfar-lab` |
| `~/src/astroai-containers` | [`astroai/astroai-containers`](https://github.com/astroai/astroai-containers) | `containers` |
| `~/src/astroai-workload` | [`astroai/astroai-workload`](https://github.com/astroai/astroai-workload) | `sfabbro/astroai-workload` |

## Local remotes

```bash
git -C ~/src/astroai-lab remote set-url origin https://github.com/astroai/astroai-lab.git
git -C ~/src/astroai-workload remote set-url origin https://github.com/astroai/astroai-workload.git
git -C ~/src/astroai-containers remote set-url origin https://github.com/astroai/astroai-containers.git
```

## CANFAR adoption packet (optional)

If CANFAR staff want to adopt AstroAI session images later:

- Images: already published under Harbor project `astroai`.
- Docs: point users at `astroai-lab guide` + storage tiers (`/scratch`, `/arc`, `vos:`).
- No OpenCADC `canfar` / `science-platform` code changes are required for this stack.
- Ray: stock Dashboard + headless workers; custom manager UI is frozen.

## Explicit non-goals

- Forking or patching `opencadc/canfar` / `opencadc/science-platform`.
- Keeping a forever `canfar-lab` CLI alias.
- Building a long-term custom Ray web console.
