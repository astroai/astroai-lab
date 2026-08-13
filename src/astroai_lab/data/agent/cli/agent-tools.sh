# Pre-installed on AstroAI lab (use these names directly — no custom wrappers):
#   rg  fd  fzf  bat  peek  jq  gh  pixi  uv  hyperfine
#   canfar  cadcget  cadc-tap  vcp  astroai-lab  — /opt/astroai/venv/cadc/bin
#   sg  —  astroai-lab agent plugins install ast-grep-cli
#
# pixi project:  pixi install && pixi run python script.py  (versions in pixi.lock)
# uv project:    uv sync && uv run python script.py          (versions in uv.lock)
#
# Platform CLI upgrade (this session):  upgrade-cadc-tools.sh --upgrade astroai-lab
# Agent overview:                       astroai-lab agent list
# Plugins (skills/MCP/rules/tools):     astroai-lab agent plugins list
# Plugins (e.g. ponytail):              astroai-lab agent plugins install ponytail
# Agent configs refresh:                astroai-lab agent update
# Config syntax check / repair:         astroai-lab agent verify · agent verify --fix
#
# Default agent setup:  astroai-lab agent setup cursor  (default plugins only)
# Opt-in skills:        astroai-lab agent plugins install polars  (see skills-sources.json)
# Bulk via pixi:        pixi global install pixi-skills && pixi-skills manage --backend cursor
