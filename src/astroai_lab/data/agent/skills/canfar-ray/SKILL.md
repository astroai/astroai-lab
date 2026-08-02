---
name: canfar-ray
description: >-
  Drive CANFAR Ray clusters from a session — ensure/status/stop/scale a
  ray-manager, fetch the Ray Dashboard URL, and (optionally) enable the native
  Ray autoscaler. Use when the user asks to start, check, resize, or tear down
  Ray batch compute on AstroAI / CANFAR.
---

# CANFAR Ray clusters with `astroai-workload`

Everything goes through one CLI: **`astroai-workload`** (installed in every
AstroAI session image). It talks to the CANFAR ray-manager session over the
platform API and prints plain-text or `--json` output.

```bash
export PATH="/opt/astroai/venv/cadc/bin:$PATH"   # if not already on PATH
astroai-workload --help
astroai-workload cluster --help
```

> `astroai-workload` is the CLI. The session's Ray **Jobs API / Dashboard**
> live on the manager's connect URL, exported as `ASTROAI_RAY_JOBS_ADDRESS`
> after `ensure`. Use the Ray Jobs API (`ray job submit`) against that address
> to run actual workloads — this skill covers cluster lifecycle.

## Start / ensure a cluster (one-click)

`ensure` finds the ray-manager session (env → persisted URL → `canfar ps`
discovery), waits for it to be ready, optionally launches workers, and prints
the Jobs + Dashboard address:

```bash
astroai-workload cluster ensure                          # manager only, no workers
astroai-workload cluster ensure --workers 2              # manager + 2 workers
astroai-workload cluster ensure --workers 2 --cores 2 --ram 8 --gpus 0
astroai-workload cluster ensure --workers 1 --gpus 1 --timeout 1800
```

Output includes:

```
manager:     <manager URL>
jobs/dash:   <manager URL>/dashboard
phase:       Running  joined: 2
export ASTROAI_RAY_JOBS_ADDRESS=<manager URL>/dashboard
```

Machine-readable variant: `astroai-workload cluster ensure --workers 2 --json`
returns `{manager_url, jobs_address, dashboard_url, cluster_phase, joined_workers, worker_count}`.

Use `--address` to target a specific manager: `--address <manager URL>` (or set
`ASTROAI_RAY_JOBS_ADDRESS`). Default `--timeout` is 1800 s — wait for the
manager, don't give up on the first poll.

## Status

```bash
astroai-workload cluster status                 # phase, ray address, joined/total
astroai-workload cluster status --json
```

`joined: N / M` is the key health number — it shows how many worker sessions
have actually joined the Ray cluster. `auth: ok` means the session holds valid
CANFAR credentials.

## Scale up / down

```bash
astroai-workload cluster scale 4                # grow or shrink to 4 workers
astroai-workload cluster scale 1 --cores 2 --ram 8
astroai-workload cluster scale 0                # shut down all workers (keep manager)
```

`scale` launches new worker sessions when below target and destroys joined
excess workers when above. Wait for the operation with the default timeout.

## Stop / tear down

```bash
astroai-workload cluster stop                    # stop cluster + destroy all workers
astroai-workload cluster stop --json
```

## Dashboard

```bash
astroai-workload dashboard url           # full Ray Dashboard URL
astroai-workload dashboard proxy         # proxy URL for this session
astroai-workload dashboard iframe        # HTML iframe snippet (embed in a notebook/marimo)
```

Open the URL in the session's browser to see the native Ray UI (jobs, nodes,
metrics). In a notebook/marimo session use the `iframe` output.

## Autoscaler (optional, on-demand workers)

For true on-demand scaling (workers appear when Ray needs them), write an
autoscaling YAML and let Ray manage it:

```bash
astroai-workload autoscaler write-config \
    --path /tmp/autoscaling.yaml \
    --cluster-name default \
    --max-workers 8 \
    --cores 2 --ram-gb 8

ray start --head --autoscaling-config=/tmp/autoscaling.yaml
```

Ray's own autoscaler then launches/destroys `ray-worker` CANFAR sessions
between the configured minimum and `--max-workers`.

## Golden rules for agents

1. **Prefer `--json`** when parsing results programmatically; plain text when
   showing the user.
2. **`ensure` is idempotent** — safe to call before every job if the user
   wants a cluster guaranteed up.
3. **Jobs go on Ray, lifecycle goes through `astroai-workload`.** After
   `ensure`, submit with the Ray Jobs API / `ray job submit --address
   $ASTROAI_RAY_JOBS_ADDRESS`.
4. **Clean up.** If you scaled up workers, offer to `cluster scale` back down
   or `cluster stop` when the batch work finishes — CANFAR sessions are billed.
5. **Don't poll forever.** `ensure`/`scale` already wait; give the user the
   dashboard URL if the cluster is slow to join.
