# Optional configuration

**Zero config by default.** Paths resolve from session environment variables (`TMP_SRC_DIR`, `TMP_SCRATCH_DIR`) and standard CANFAR mount points.

Optional preferences live at **`~/.canfar/lab/config.yaml`**. All keys are optional.

```yaml
# example
default_pm: pixi          # pixi | uv
clone_from_env: ml-base   # default --from-env name
push:
  auto_save: true
  require_clean_git: false
```

Environment variables override YAML (prefix **`CANFAR_LAB_`**):

| Variable | YAML key |
|----------|----------|
| `CANFAR_LAB_WORK_DIR` | `work_dir` |
| `CANFAR_LAB_SCRATCH_DIR` | `scratch_dir` |
| `CANFAR_LAB_SAVE_DIR` | `save_dir` |
| `CANFAR_LAB_DEFAULT_PM` | `default_pm` |
| `CANFAR_LAB_CLONE_FROM_ENV` | `clone_from_env` |
| `CANFAR_LAB_PUSH__AUTO_SAVE` | `push.auto_save` |
| `CANFAR_LAB_PUSH__REQUIRE_CLEAN_GIT` | `push.require_clean_git` |

Inspect current settings:

```bash
canfar-lab config show
canfar-lab config path
canfar-lab --json config show
```

Per-project config inside git repos is intentionally **not** supported — keeps OSS repos portable.
