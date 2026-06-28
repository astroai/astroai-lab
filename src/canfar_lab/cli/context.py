from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GlobalOpts:
    json: bool = False
    yes: bool = False
    dry_run: bool = False
    quiet: bool = False


def get_opts(ctx) -> GlobalOpts:
    return ctx.obj if isinstance(ctx.obj, GlobalOpts) else GlobalOpts()
