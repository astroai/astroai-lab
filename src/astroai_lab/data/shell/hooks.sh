#!/bin/bash
# Session reminders and exit hooks for AstroAI lab (interactive shells only).

__astroai_lab_state_dir() {
    echo "${ASTROAI_LAB_CONFIG_DIR:-${HOME}/.astroai/lab}"
}

__astroai_lab_scratch_dir() {
    echo "${TMP_SCRATCH_DIR:-${ASTROAI_LAB_DEFAULT_SCRATCH_DIR:-/scratch}}"
}

__astroai_lab_scratch_reminder() {
    local _state _start_file _reminder_file _interval=7200

    [[ -t 1 ]] || return 0
    _state="$(__astroai_lab_state_dir)"
    _start_file="${_state}/session-started"
    _reminder_file="${_state}/last-reminder"
    [[ -f "${_start_file}" ]] || return 0

    local _start _now _elapsed _last _since_last
    _start="$(cat "${_start_file}" 2>/dev/null)" || return 0
    [[ -n "${_start}" && "${_start}" -gt 0 ]] || return 0

    printf -v _now '%(%s)T' -1
    _elapsed=$(( _now - _start ))
    (( _elapsed >= _interval )) || return 0

    _last=0
    [[ -f "${_reminder_file}" ]] && _last="$(cat "${_reminder_file}" 2>/dev/null)" || true
    _since_last=$(( _now - _last ))
    (( _since_last >= _interval )) || return 0

    local _hours=$(( _elapsed / 3600 )) _mins=$(( (_elapsed % 3600) / 60 )) _summary="" _part

    if [[ -d "$(__astroai_lab_scratch_dir)" ]]; then
        _part="$(df -h "$(__astroai_lab_scratch_dir)" 2>/dev/null | awk 'NR>1 {print $3}')"
        [[ -n "${_part}" ]] && _summary="${_summary}data: ${_part}"
    fi

    if git rev-parse --is-inside-work-tree &>/dev/null; then
        _part="$(git rev-list --count HEAD --since="@${_start}" 2>/dev/null)"
        if [[ -n "${_part}" && "${_part}" -gt 0 ]]; then
            [[ -n "${_summary}" ]] && _summary="${_summary} | "
            _summary="${_summary}commits: ${_part}"
        fi
    fi

    if [[ -n "${_summary}" ]]; then
        printf '\n  \033[1;33m⏳ %dh %dm (%s)\033[0m\n  → git push or astroai-lab --yes push (${TMP_SRC_DIR} is ephemeral)\n\n' \
            "${_hours}" "${_mins}" "${_summary}"
    else
        printf '\n  \033[1;33m⏳ %dh %dm — git push or astroai-lab --yes push (${TMP_SRC_DIR} is ephemeral)\033[0m\n\n' \
            "${_hours}" "${_mins}"
    fi

    mkdir -p "${_state}"
    printf '%s' "${_now}" > "${_reminder_file}"
}

__astroai_lab_quota_used_pct() {
    local path="${1:-}"
    [[ -d "${path}" ]] || return 0
    df "${path}" 2>/dev/null | awk 'NR>1 {used=$3; size=$2; if(size>0) printf "%.0f", (used/size)*100; else print 0}'
}

__astroai_lab_quota_reminder() {
    local _state _reminder_file _interval=21600

    [[ -t 1 ]] || return 0
    [[ -d "${HOME}" ]] || return 0

    _state="$(__astroai_lab_state_dir)"
    _reminder_file="${_state}/last-quota-reminder"

    local _now _last _since_last
    printf -v _now '%(%s)T' -1
    _last=0
    [[ -f "${_reminder_file}" ]] && _last="$(cat "${_reminder_file}" 2>/dev/null)" || true
    _since_last=$(( _now - _last ))
    (( _since_last >= _interval )) || return 0

    local _used_pct
    _used_pct="$(__astroai_lab_quota_used_pct "${HOME}")"
    [[ -n "${_used_pct}" ]] || return 0

    mkdir -p "${_state}"
    printf '%s' "${_now}" > "${_reminder_file}"
    (( _used_pct >= 80 )) || return 0

    local _level _color
    if (( _used_pct >= 95 )); then
        _level="CRITICAL"
        _color='\033[1;31m'
    elif (( _used_pct >= 90 )); then
        _level="high"
        _color='\033[1;33m'
    else
        _level="monitor"
        _color='\033[1;33m'
    fi
    printf '\n  %b⚠  home: %d%% used (%s) — astroai-lab clean home --all-safe%b\n\n' \
        "${_color}" "${_used_pct}" "${_level}" '\033[0m'
}

__astroai_lab_backup_reminder() {
    local _state _status _interval=21600 _now _last _since_last

    [[ -t 1 ]] || return 0
    _state="$(__astroai_lab_state_dir)"
    _status="${_state}/backup-status.json"
    [[ -f "${_status}" ]] || return 0

    printf -v _now '%(%s)T' -1
    _last=0
    [[ -f "${_state}/last-backup-reminder" ]] && _last="$(cat "${_state}/last-backup-reminder" 2>/dev/null)" || true
    _since_last=$(( _now - _last ))
    (( _since_last >= _interval )) || return 0

    if ! command -v jq >/dev/null 2>&1; then
        return 0
    fi
    local _ok _skipped _msg
    _ok="$(jq -r '.ok // empty' "${_status}" 2>/dev/null)" || return 0
    _skipped="$(jq -r '.skipped // false' "${_status}" 2>/dev/null)"
    _msg="$(jq -r '.message // empty' "${_status}" 2>/dev/null)"
    [[ "${_ok}" == "true" ]] && return 0

    mkdir -p "${_state}"
    printf '%s' "${_now}" > "${_state}/last-backup-reminder"
    if [[ "${_skipped}" == "true" ]]; then
        printf '\n  \033[1;33m⚠  work backup skipped — %s\033[0m\n  → astroai-lab clean home --all-safe  or  ASTROAI_LAB_BACKUP_INTERVAL\n\n' "${_msg}"
    else
        printf '\n  \033[1;33m⚠  work backup failed — %s\033[0m\n  → astroai-lab backup status\n\n' "${_msg}"
    fi
}

__astroai_lab_auto_archive() {
    local _root _hash _marker _log _state

    git rev-parse --is-inside-work-tree &>/dev/null || return 0
    _root="$(git rev-parse --show-toplevel 2>/dev/null)" || return 0
    _hash="$(printf '%s' "${_root}" | sha256sum | awk '{print $1}')"
    _state="$(__astroai_lab_state_dir)"
    _marker="${_state}/auto-archived-${_hash}"
    _log="${_state}/auto-archive.log"

    [[ -f "${_marker}" ]] && return 0

    mkdir -p "${_state}"
    touch "${_marker}"
    if astroai-lab --yes push >>"${_log}" 2>&1; then
        return 0
    fi
    rm -f "${_marker}"
}

__astroai_lab_on_exit() {
    __astroai_lab_auto_archive
    if [[ -n "${__ASTROAI_LAB_PRIOR_EXIT_TRAP:-}" ]]; then
        eval "${__ASTROAI_LAB_PRIOR_EXIT_TRAP}"
    fi
}

if [[ -t 1 ]]; then
    __ASTROAI_LAB_PRIOR_EXIT_TRAP="$(
        trap -p EXIT 2>/dev/null | sed -n "s/^trap -- '\(.*\)' EXIT\$/\1/p" || true
    )"
    if [[ -z "${__ASTROAI_LAB_PRIOR_EXIT_TRAP}" || "${__ASTROAI_LAB_PRIOR_EXIT_TRAP}" == "__astroai_lab_on_exit" ]]; then
        unset __ASTROAI_LAB_PRIOR_EXIT_TRAP
    fi
    trap __astroai_lab_on_exit EXIT
fi

if [[ -t 1 ]]; then
    if [[ -z "${PROMPT_COMMAND:-}" ]]; then
        PROMPT_COMMAND="__astroai_lab_scratch_reminder; __astroai_lab_quota_reminder; __astroai_lab_backup_reminder"
    else
        PROMPT_COMMAND="${PROMPT_COMMAND}; __astroai_lab_scratch_reminder; __astroai_lab_quota_reminder; __astroai_lab_backup_reminder"
    fi
fi
