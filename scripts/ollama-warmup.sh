#!/usr/bin/env bash
# Best-effort local LLM warmup for prompt improvement hooks.

set -u

[ "${PROMPT_IMPROVER_WARMUP:-1}" = "0" ] && exit 0
command -v ollama >/dev/null 2>&1 || exit 0

LOG_DIR="$HOME/.ollama/logs"
LOG_FILE="$LOG_DIR/ollama-serve.log"
PID_FILE="$HOME/.ollama/ollama-serve.pid"
MODEL="${OLLAMA_IMPROVE_WARM_MODEL:-cryptidbleh/gemma4-claude-opus-4.6:latest}" # keep in sync with _DEFAULT_IMPROVE_CHAIN primary (shared/config.py)

mkdir -p "$LOG_DIR"

ollama_up() {
    curl -fsS --max-time 1 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1
}

if ! ollama_up; then
    started=0
    # Native Ubuntu: the daemon is a systemd service — start it through the
    # service manager so supervision/logging stay managed. Fall back to a
    # detached `ollama serve` only where no unit exists (WSL, containers).
    if command -v systemctl >/dev/null 2>&1; then
        if systemctl --user cat ollama.service >/dev/null 2>&1; then
            systemctl --user start ollama >/dev/null 2>&1 && started=1
        elif systemctl cat ollama.service >/dev/null 2>&1; then
            systemctl start ollama >/dev/null 2>&1 && started=1
        fi
    fi
    if [ "$started" = "0" ]; then
        (
            nohup ollama serve >>"$LOG_FILE" 2>&1 &
            echo $! >"$PID_FILE"
        ) >/dev/null 2>&1
    fi
    # Wait for readiness (bounded) so the preload below actually warms the model.
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        ollama_up && break
        sleep 0.5
    done
fi

if [ "${PROMPT_IMPROVER_PRELOAD:-1}" != "0" ]; then
    (timeout 25 ollama run "$MODEL" "Reply with OK only." >/dev/null 2>>"$LOG_FILE" || true) &
fi

exit 0
