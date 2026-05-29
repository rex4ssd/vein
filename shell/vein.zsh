# vein.zsh — zsh shell integration for vein
#
# Install:
#   echo 'source /Users/lion/Documents/vein/shell/vein.zsh' >> ~/.zshrc
#   source ~/.zshrc
#
# What this adds:
#   vt          — triage last failed command (vein pipe --ai)
#   vr <cmd>    — vein run shorthand
#   vp          — vein pipe shorthand
#   vein brief  — already works, but alias vb for speed

# ── track last command + exit code ───────────────────────────────

_VEIN_LAST_CMD=""
_VEIN_LAST_CODE=0

_vein_precmd() {
    _VEIN_LAST_CODE=$?
    # fc -ln -1: last command in history, no line number
    _VEIN_LAST_CMD=$(fc -ln -1 2>/dev/null | sed 's/^[[:space:]]*//' || true)
}

autoload -Uz add-zsh-hook
add-zsh-hook precmd _vein_precmd

# ── vt: triage last failed command ───────────────────────────────

vt() {
    if [[ $_VEIN_LAST_CODE -eq 0 ]]; then
        echo "[vein] last command succeeded (exit 0) — nothing to triage"
        return 0
    fi

    local cmd="$_VEIN_LAST_CMD"
    echo "[vein] triaging: $cmd  (exit $_VEIN_LAST_CODE)"
    echo ""

    # re-run the command, pipe output to vein pipe
    # pass any extra flags through (e.g. vt --ai, vt --log)
    eval "$cmd" 2>&1 | vein pipe --cmd "$cmd" "$@"
}

# ── vf: vein fail — manually pipe clipboard or last error ────────
# Usage: copy error in terminal → vf --ai

vf() {
    # read from stdin if piped, else prompt
    if [[ -p /dev/stdin ]]; then
        vein pipe "$@"
    else
        echo "[vein] Paste the error (^D when done):"
        vein pipe "$@"
    fi
}

# ── shortcuts ─────────────────────────────────────────────────────

alias vr='vein run'
alias vp='vein pipe'
alias vb='vein brief'
alias vs='vein status'
alias vl='vein log'
alias va='vein ask'
alias vrc='vein recall'

# ── autocomplete (only if compinit already ran) ───────────────────

if command -v vein &>/dev/null && (( ${+functions[compdef]} )); then
    eval "$(_VEIN_COMPLETE=zsh_source vein 2>/dev/null || true)"
fi
