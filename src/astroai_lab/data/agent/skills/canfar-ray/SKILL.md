---
name: canfar-ray
description: >-
  Drive a CANFAR Ray cluster and run jobs on it with astroai-workload:
  cluster ensure/status/scale/stop, dashboard URL, and run/submit/list/logs.
  Use when the user wants batch compute, Ray workers, or to run a script on
  an existing Ray cluster.
---

# CANFAR Ray with `astroai-workload`

One CLI. Installed on AstroAI session images.

```bash
astroai-workload --help
```

There are two different actions. Do not mix them up.

1. **Workers** (`cluster …`). Start or resize the machines that join Ray.
   Does not create the ray-manager session. The user starts that from the
   AstroAI hub (**Start batch compute**) or the portal first.
2. **Jobs** (`run` / `submit`). Run a program on a cluster that is already
   up. Does not start workers.

Autoscaling (Ray starts and stops workers by itself) is
`autoscaler write-config` on the manager head. Do not use that for a normal
"run my script" request. Prefer `cluster ensure --workers N`.

Do not call `ray job submit`. The job command is `astroai-workload run`.

## Start workers

```bash
astroai-workload cluster ensure --workers 2
astroai-workload cluster ensure --workers 2 --cores 2 --ram 8
astroai-workload cluster ensure --workers 1 --gpus 1 --timeout 1800
```

Prints `export ASTROAI_RAY_JOBS_ADDRESS=…`. The caller must export it in
their shell (a CLI cannot export into the parent). `--json` returns
`manager_url`, `jobs_address`, `dashboard_url`, `cluster_phase`,
`joined_workers`.

`ensure` does not create the manager. If none exists, tell the user to use
the hub, then retry.

## Run a job

```bash
export ASTROAI_RAY_JOBS_ADDRESS=…    # from ensure; skip inside the manager
astroai-workload run train.py --cpus 2
astroai-workload submit --cmd 'python -m mosaic.stack --in /arc/projects/g/in' --wait
astroai-workload list
astroai-workload logs <run-id>
```

`--input` / `--output` URIs are stored on the Ray job. They are not copied.
Put data on `/arc`. `/scratch` dies with the session.

## Status, scale, stop, dashboard

```bash
astroai-workload cluster status
astroai-workload cluster scale 4
astroai-workload cluster scale 0     # stop workers, keep the manager
astroai-workload cluster stop
astroai-workload dashboard url
astroai-workload dashboard iframe    # notebook / marimo
```

`joined: N / M` is the health number. `auth: ok` means CANFAR credentials
are present.

## Autoscaling (manager head only)

Only when the user asked for workers that come and go with load:

```bash
astroai-workload autoscaler write-config \
    --path /tmp/autoscaling.yaml \
    --cluster-name default --max-workers 8 --cores 2 --ram-gb 8
```

That file is for `ray start --head --autoscaling-config=…` on the manager.
A notebook session cannot usefully run that.

## Rules for agents

1. Prefer `--json` when you will parse. Plain text when showing the user.
2. `ensure` is safe to call again. It does not create a second manager.
3. After `ensure`, jobs are `astroai-workload run` (or `submit --cmd`).
4. Workers cost money. Offer `cluster scale 0` or `cluster stop` when the
   batch work is done.
5. `ensure` / `scale` already wait. If join is slow, give the user
   `dashboard url` instead of polling forever.
6. MCP `job_*` tools need Ray. Cluster tools do not. Same CLI functions
   either way.
