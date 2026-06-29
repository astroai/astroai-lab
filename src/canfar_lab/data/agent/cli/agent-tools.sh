# Pre-installed on CANFAR lab (use these names directly — no custom wrappers):
#   rg  fd  fzf  bat  jq  gh  pixi  uv  hyperfine
#   canfar  cadcget  cadc-tap  vcp  canfar-lab  — /opt/astroai/venv/cadc/bin
#   sg  —  canfar-lab agent install ast-grep
#
# pixi project:  pixi install && pixi run python script.py  (versions in pixi.lock)
# uv project:    uv sync && uv run python script.py          (versions in uv.lock)
#
# Platform CLI upgrade (this session):  upgrade-cadc-tools.sh --upgrade canfar-lab
# Agent bundles refresh:                canfar-lab agent update
#
# Agent skills from GitHub:  canfar-lab agent setup cursor  (see skills-sources.json)
# More skills via pixi:      pixi global install pixi-skills && pixi-skills manage --backend cursor
