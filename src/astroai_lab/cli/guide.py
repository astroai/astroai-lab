from __future__ import annotations

from astroai_lab.utils.console import console

GUIDE_TEXT = """
[bold]astroai-lab[/bold] — in-session workbench for AstroAI on CANFAR

[bold]Names[/bold]
  canfar           platform CLI — login, create sessions, images
  astroai-lab      this tool — projects, env, paths, data, agents (inside a session)
  AstroAI          product (images + tools); CANFAR is the Science Platform

[bold]Storage tiers[/bold]
  work dir        ephemeral code (TMP_SRC_DIR, default /srcdir)
  scratch         ephemeral data + download caches (TMP_SCRATCH_DIR, /scratch)
  /arc/home       persistent config and env saves (~/.astroai/lab/saves)
  /arc/projects   team persistent storage

[bold]Session loop[/bold]
  1. astroai-lab resume mylab       # or init / clone
  2. cd $WORK/mylab && pixi run python analysis.py
  3. astroai-lab save               # anytime
  4. astroai-lab push               # git push + env save before closing

[bold]Daily commands[/bold]
  astroai-lab                       brief status + next step
  astroai-lab init mylab            new pixi/uv project
  astroai-lab clone owner/repo      gh clone + install
  astroai-lab save [name]           lockfile manifest → /arc
  astroai-lab resume NAME           restore saved env
  astroai-lab saves                 list saved envs
  astroai-lab push                  end-of-session archive (astroai-lab push --yes)
  astroai-lab status --json         quotas, team projects, GMS/vault, canfar auth/ps, processes
  astroai-lab kernel ensure         notebook scratch-safe kernel
  astroai-lab notebook starter
  astroai-lab doctor --json         paths, caches, tools

[bold]Platform tools[/bold]
  /opt/astroai/venv/cadc           canfar, cadcget, astroai-lab (writable this session)
  upgrade-cadc-tools.sh            bump platform CLIs this session

[bold]Flags[/bold]
  --json --yes --dry-run           before or on subcommands (e.g. clean home --dry-run)

[bold]Data[/bold]
  astroai-lab data stage SRC [DST]  /arc → scratch (fast I/O)
  astroai-lab data sync SRC DST     scratch → /arc

[bold]Hygiene[/bold]
  astroai-lab clean home --all-safe --dry-run
  astroai-lab clean cache --all-safe

[bold]Portable projects[/bold]
  Published repos use standard pixi.toml / pyproject.toml only.
  astroai-lab clone --from-env is session-local bootstrap only.

[bold]Config[/bold] (optional)
  ~/.astroai/lab/config.yaml        preferences only
  astroai-lab config show|path

[bold]More[/bold]
  https://opencadc.github.io/canfar/
  https://github.com/astroai/astroai-lab
"""


def print_guide() -> None:
    console.print(GUIDE_TEXT)
