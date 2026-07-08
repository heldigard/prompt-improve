#!/usr/bin/env bash
# Best-effort local LLM warmup for prompt improvement hooks.

set -u

[ "${PROMPT_IMPROVER_WARMUP:-1}" = "0" ] && exit 0
command -v ollama >/dev/null 2>&1 || exit 0

LOG_DIR="$HOME/.ollama/logs"
LOG_FILE="$LOG_DIR/ollama-serve.log"
PID_FILE="$HOME/.ollama/ollama-serve.pid"
MODEL="${OLLAMA_IMPROVE_WARM_MODEL:-SetneufPT/Qwopus3.5-4B-Coder-MTP_Q4_64k_8GB-GPU:latest}" # 2026-07-08 canonical refactor: improve PRIMARY.

mkdir -p "$LOG_DIR"

if ! curl -fsS --max-time 1 "http://127.0.0.1:11434/api/tags" >/dev/null 2>&1; then
    (
        nohup ollama serve >>"$LOG_FILE" 2>&1 &
        echo $! >"$PID_FILE"
    ) >/dev/null 2>&1
    sleep 0.5
fi

if [ "${PROMPT_IMPROVER_PRELOAD:-1}" != "0" ]; then
    (timeout 25 ollama run "$MODEL" "Reply with OK only." >/dev/null 2>>"$LOG_FILE" || true) &
fi

exit 0
