from __future__ import annotations

from canfar_lab.utils.console import console

GUIDE_TEXT = """
[bold]canfar-lab[/bold] — CANFAR Science Platform in-session workbench

[bold]Relationship to canfar[/bold]
  canfar          authenticate, create sessions, manage images (outside or inside)
  canfar-lab      day-to-day work inside a running session

[bold]Storage tiers[/bold]
  work dir        ephemeral code (TMP_SRC_DIR, default /srcdir)
  scratch         ephemeral data + download caches (TMP_SCRATCH_DIR, /scratch)
  /arc/home       persistent config and env saves (~/.canfar/lab/saves)
  /arc/projects   team persistent storage

[bold]Session loop[/bold]
  1. canfar-lab resume mylab       # or init / clone
  2. cd $WORK/mylab && pixi run python analysis.py
  3. canfar-lab save               # anytime
  4. canfar-lab push               # git push + env save before closing

[bold]Daily commands[/bold]
  canfar-lab                       brief status + next step
  canfar-lab init mylab            new pixi/uv project
  canfar-lab clone owner/repo      gh clone + install
  canfar-lab save [name]           lockfile manifest → /arc
  canfar-lab resume NAME           restore saved env
  canfar-lab saves                 list saved envs
  canfar-lab push                  end-of-session archive (canfar-lab push --yes)
  canfar-lab status --json         quotas, canfar auth/ps, processes
  canfar-lab doctor --json         paths, caches, tools

[bold]Platform tools[/bold]
  /opt/astroai/venv/cadc           canfar, cadcget, canfar-lab (writable this session)
  upgrade-cadc-tools.sh            bump platform CLIs without a new image

[bold]Flags[/bold]
  --json --yes --dry-run           before or on subcommands (e.g. clean home --dry-run)

[bold]Data[/bold]
  canfar-lab data stage SRC [DST]  /arc → scratch (fast I/O)
  canfar-lab data sync SRC DST     scratch → /arc

[bold]Hygiene[/bold]
  canfar-lab clean home --all-safe --dry-run
  canfar-lab clean cache --all-safe

[bold]Portable OSS projects[/bold]
  Published repos use standard pixi.toml / pyproject.toml only.
  canfar-lab clone --from-env is session-local bootstrap only.

[bold]Config[/bold] (optional)
  ~/.canfar/lab/config.yaml        preferences only
  canfar-lab config show|path

[bold]More[/bold]
  https://opencadc.github.io/canfar/
"""


def print_guide() -> None:
    console.print(GUIDE_TEXT)
