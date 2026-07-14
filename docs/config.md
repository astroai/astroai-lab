# Optional configuration

Paths resolve from session environment variables (`TMP_SRC_DIR`, `TMP_SCRATCH_DIR`)
and standard CANFAR mount points. Optional preferences live at
**`~/.astroai/lab/config.yaml`**. Every key is optional.

```yaml
# example
default_pm: pixi          # pixi | uv
clone_from_env: ml-base   # default --from-env name
push:
  auto_save: true
  require_clean_git: false
```

Environment variables override YAML (prefix **`ASTROAI_LAB_`**):

| Variable | YAML key |
|----------|----------|
| `ASTROAI_LAB_WORK_DIR` | `work_dir` |
| `ASTROAI_LAB_SCRATCH_DIR` | `scratch_dir` |
| `ASTROAI_LAB_SAVE_DIR` | `save_dir` |
| `ASTROAI_LAB_DEFAULT_PM` | `default_pm` |
| `ASTROAI_LAB_CLONE_FROM_ENV` | `clone_from_env` |
| `ASTROAI_LAB_PUSH__AUTO_SAVE` | `push.auto_save` |
| `ASTROAI_LAB_PUSH__REQUIRE_CLEAN_GIT` | `push.require_clean_git` |

Inspect current settings:

```bash
astroai-lab config show
astroai-lab config path
astroai-lab --json config show
```

Workbench settings stay in `~/.astroai/lab/` so published git repos remain
portable (`pixi.toml` / `pyproject.toml` only).
