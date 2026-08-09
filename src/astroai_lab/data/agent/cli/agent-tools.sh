# Pre-installed on AstroAI lab (use these names directly — no custom wrappers):
#   rg  fd  fzf  bat  peek  jq  gh  pixi  uv  hyperfine
#   canfar  cadcget  cadc-tap  vcp  astroai-lab  — /opt/astroai/venv/cadc/bin
#   sg  —  astroai-lab agent install ast-grep
#
# pixi project:  pixi install && pixi run python script.py  (versions in pixi.lock)
# uv project:    uv sync && uv run python script.py          (versions in uv.lock)
#
# Platform CLI upgrade (this session):  upgrade-cadc-tools.sh --upgrade astroai-lab
# Agent overview:                       astroai-lab agent list
# Configs (skills/MCP/addons):          astroai-lab agent list config
# Plugins (e.g. ponytail):              astroai-lab agent plugins install ponytail
# Agent configs refresh:                astroai-lab agent update
# Config syntax check / repair:         astroai-lab agent verify · agent repair
#
# Agent skills from GitHub:  astroai-lab agent setup cursor  (see skills-sources.json)
# More skills via pixi:      pixi global install pixi-skills && pixi-skills manage --backend cursor
