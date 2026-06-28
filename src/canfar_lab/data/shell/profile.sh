#!/bin/bash
# CANFAR lab session environment — sourced from /etc/canfar-lab/profile.sh
# Image-specific PATH (/opt/astroai/...) is applied in /etc/profile.d/astroai.sh.

[[ -n "${BASH_VERSION:-}" ]] || return 0 2>/dev/null || exit 0

if [[ -n "${CANFAR_LAB_PROFILE_LOADED:-}" ]]; then
    return 0 2>/dev/null || true
fi
CANFAR_LAB_PROFILE_LOADED=1

if command -v canfar-lab >/dev/null 2>&1; then
    # shellcheck disable=SC1090
    eval "$(canfar-lab env export 2>/dev/null)" || true
else
    echo "canfar-lab: command not found — session paths may be incomplete" >&2
fi

if [[ -n "${CANFAR_LAB_PATH_PREFIX:-}" ]]; then
    case ":${PATH}:" in
        *":${CANFAR_LAB_PATH_PREFIX}:"*) ;;
        *) export PATH="${CANFAR_LAB_PATH_PREFIX}:${PATH}" ;;
    esac
fi

_CANFAR_LAB_SHELL_DIR="${CANFAR_LAB_SHELL_DIR:-/etc/canfar-lab}"
if [[ -f "${_CANFAR_LAB_SHELL_DIR}/hooks.sh" ]]; then
    # shellcheck disable=SC1091
    source "${_CANFAR_LAB_SHELL_DIR}/hooks.sh"
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
