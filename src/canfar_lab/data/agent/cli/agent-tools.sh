# Pre-installed on CANFAR lab (use these names directly — no custom wrappers):
#   rg  fd  fzf  bat  jq  gh  pixi  uv  hyperfine
#   sg  —  canfar-lab agent install ast-grep
#
# pixi project:  pixi install && pixi run python script.py
# uv project:   uv sync && uv run python script.py
#
# Agent skills from GitHub:  canfar-lab agent setup cursor  (see config/agent/skills-sources.json)
# More skills via pixi:     pixi global install pixi-skills && pixi-skills manage --backend cursor
