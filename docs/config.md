# Optional configuration

Paths resolve from Slurm-style session environment variables (`WORK`, `SCRATCH`,
`PROJECT`) and standard CANFAR mount points. Optional preferences live at
**`~/.astroai/lab/config.yaml`**. Every key is optional.

```yaml
# example
default_pm: pixi          # pixi | uv
clone_from_env: ml-base   # default --from-env name
```

Environment variables override YAML:

| Variable | YAML key |
|----------|----------|
| `WORK` | `work_dir` |
| `SCRATCH` | `scratch_dir` |
| `ASTROAI_LAB_SAVE_DIR` | `save_dir` |
| `ASTROAI_LAB_DEFAULT_PM` | `default_pm` |
| `ASTROAI_LAB_CLONE_FROM_ENV` | `clone_from_env` |

Inspect current settings:

```bash
astroai config show
astroai config path
astroai --json config show
```

Workbench settings stay in `~/.astroai/lab/` so published git repos remain
portable (`pixi.toml` / `pyproject.toml` only).
