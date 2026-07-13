#!/bin/bash
# AstroAI lab session environment — sourced from /etc/astroai-lab/profile.sh
# Image PATH (/opt/astroai/...) is applied in /etc/profile.d/astroai.sh after export.

[[ -n "${BASH_VERSION:-}" ]] || return 0 2>/dev/null || exit 0

if [[ -n "${ASTROAI_LAB_PROFILE_LOADED:-}" ]]; then
    return 0 2>/dev/null || true
fi
ASTROAI_LAB_PROFILE_LOADED=1

if command -v astroai-lab >/dev/null 2>&1; then
    _astroai_lab_cli="astroai-lab"
elif [[ -x /opt/astroai/venv/cadc/bin/astroai-lab ]]; then
    _astroai_lab_cli="/opt/astroai/venv/cadc/bin/astroai-lab"
fi

if [[ -n "${_astroai_lab_cli:-}" ]]; then
    # shellcheck disable=SC1090
    eval "$("${_astroai_lab_cli}" env export)" || {
        echo "astroai-lab env export failed — session paths may be incomplete" >&2
    }
else
    echo "astroai-lab: command not found — session paths may be incomplete" >&2
fi
unset _astroai_lab_cli

_ASTROAI_LAB_SHELL_DIR="${ASTROAI_LAB_SHELL_DIR:-/etc/astroai-lab}"
if [[ -f "${_ASTROAI_LAB_SHELL_DIR}/hooks.sh" ]]; then
    # shellcheck disable=SC1091
    source "${_ASTROAI_LAB_SHELL_DIR}/hooks.sh"
fi

alias py="python3"
alias ll="ls -alF"
alias la="ls -A"

if [[ -n "${BASH_VERSION:-}" ]]; then
    command -v uv >/dev/null 2>&1 && eval "$(uv generate-shell-completion bash)"
    command -v pixi >/dev/null 2>&1 && eval "$(pixi completion --shell bash)"
    command -v gh >/dev/null 2>&1 && eval "$(gh completion -s bash)"
    command -v rg >/dev/null 2>&1 && eval "$(rg --generate complete-bash)"
    command -v fzf >/dev/null 2>&1 && eval "$(fzf --bash)"
fi
