"""Configuration constants, env vars, model registry, and regex patterns."""

from __future__ import annotations

import os
import re
from pathlib import Path

from prompt_improve.shared import compat
from prompt_improve.shared.ollama_url import normalize_ollama_url

# ---------------------------------------------------------------------------
# Ollama config
# ---------------------------------------------------------------------------
OLLAMA_URL = normalize_ollama_url(
    os.environ.get(
        "OLLAMA_URL",
        getattr(compat.ollama_client, "DEFAULT_URL", "http://127.0.0.1:11434"),
    )
)
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_IMPROVE_TIMEOUT", "45.0"))
OLLAMA_AUTOSTART = os.environ.get("OLLAMA_IMPROVE_AUTOSTART", "1") != "0"
CLOUD_FALLBACK = os.environ.get("OLLAMA_IMPROVE_CLOUD_FALLBACK", "1") != "0"
OLLAMA_LOG = os.path.expanduser("~/.ollama/logs/ollama-serve.log")
OLLAMA_PID = os.path.expanduser("~/.ollama/ollama-serve.pid")

# ---------------------------------------------------------------------------
# Model candidates (global fallback)
# ---------------------------------------------------------------------------
# Default chain = 2026-07-08 PM re-bench winners. OmniCoder is improve #1 (held;
# also bug_finding #1) -> Negentropy-claude-opus-4.7-9B (improve #2 combined) ->
# SetneufPT/Qwopus3.5-4B-Coder-MTP (tool_call/pdf_extract/structured #1) ->
# qwen3.5:4b as the small universal fallback. The full available-model tail is
# appended at runtime by choose_ollama_model_for_role, so this is prioritization,
# not a hard dependency.
_DEFAULT_IMPROVE_CHAIN = (
    "zfujicute/OmniCoder-Qwen3.5-9B-Claude-4.6-Opus-Uncensored-v2-GGUF:latest,"
    "hf.co/Jackrong/Negentropy-claude-opus-4.7-9B-GGUF:Q4_K_M,"
    "SetneufPT/Qwopus3.5-4B-Coder-MTP_Q4_64k_8GB-GPU:latest,"
    "qwen3.5:4b"
)

OLLAMA_MODEL_CANDIDATES = [
    m.strip()
    for m in os.environ.get(
        "OLLAMA_IMPROVE_MODELS",
        os.environ.get(
            "OLLAMA_IMPROVE_MODEL",
            _DEFAULT_IMPROVE_CHAIN,
        ),
    ).split(",")
    if m.strip()
]

# ---------------------------------------------------------------------------
# Task-type model registry (role → ordered candidates)
# ---------------------------------------------------------------------------
_ROLE_MODEL_MAP: dict[str, list[str]] = {}
for _role, _default in [
    ("prompt_rewrite", _DEFAULT_IMPROVE_CHAIN),
    ("prompt_clarify", _DEFAULT_IMPROVE_CHAIN),
]:
    _env_key = f"OLLAMA_IMPROVE_ROLE_{_role.upper()}"
    _ROLE_MODEL_MAP[_role] = [
        m.strip() for m in os.environ.get(_env_key, _default).split(",") if m.strip()
    ]

# ---------------------------------------------------------------------------
# Cache config
# ---------------------------------------------------------------------------
CACHE_DIR = Path.home() / ".claude" / "cache" / "prompt-improve"
CACHE_TTL_SECONDS = float(os.environ.get("OLLAMA_IMPROVE_CACHE_TTL", "300.0"))
CACHE_SCHEMA_VERSION = "prompt-improve-v18"

# ---------------------------------------------------------------------------
# Rewrite threshold
# ---------------------------------------------------------------------------
REWRITE_THRESHOLD = int(os.environ.get("OLLAMA_IMPROVE_REWRITE_THRESHOLD", "260"))

# ---------------------------------------------------------------------------
# Task verbs (EN + ES) — used by detect_trivial and hard-prompt classifier
# ---------------------------------------------------------------------------
TASK_VERBS = (
    "fix|bug|error|implement|create|build|refactor|test|deploy|debug|review|"
    "explain|show|write|update|optimize|optimiz|add|document|read|clean|find|"
    "search|investigate|audit|migrate|configure|run|lint|format|install|generate|"
    "generat|edit|modify|validate|setup|tune|profile|trace|inspect|scan|parse|"
    "evaluate|assess|estimate|plan|draft|outline|summarize|translate|convert|"
    "extract|import|export|commit|merge|revert|reset|rollback|"
    "arregla|corrige|revisa|implementa|crea|construye|despliega|prueba|analiza|"
    "analiz|configura|actualiza|borra|elimina|explica|muestra|escribe|lee|limpia|"
    "busca|encuentra|investiga|audita|migra|optimiza|documenta|ejecuta|instala|"
    "genera|edita|modifica|valida|planifica|redacta|resume|traduce|convierte|"
    "extrae|importa|exporta|envía|envia|consulta|depura|instala|compila|"
    "mejora|mejorar|amplía|amplia|extiende|simplifica|renombra|asigna"
)
TASK_VERBS_RE = re.compile(rf"\b(?:{TASK_VERBS})\b")

# ---------------------------------------------------------------------------
# Concrete file/action patterns
# ---------------------------------------------------------------------------
_CONCRETE_FILE_RE = re.compile(
    r"[^\s\"'`]\.(?:py|ts|tsx|js|jsx|mjs|cjs|java|go|rs|rb|kt|kts|cs|php|vue|svelte|"
    r"json|json5|ya?ml|toml|ini|cfg|conf|env|md|mdx|sh|bash|zsh|sql|tf|tfvars|"
    r"gradle|xml|html|htm|css|scss|proto|dockerfile)\b",
    re.IGNORECASE,
)
_CONCRETE_ACTION_RE = re.compile(
    r"\b(?:fix|edit|update|add|refactor|open|review|test|run|debug|lint|format|"
    r"build|deploy|check|migrate|implement|create|generate|arregla|edita|actualiza|"
    r"abre|revisa|corrige|despliega|construye|ejecuta|verifica|compila|migra|"
    r"implementa|crea|genera)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Hard-prompt domain signals
# ---------------------------------------------------------------------------
_HARD_DOMAIN_SIGNALS = re.compile(
    r"\b("
    r"security|seguridad|auth(?:entication|orization)?|autorizaci[oó]n|"
    r"crypto|cryptograph|encrypt|des?crypt|oauth|sso|jwt|sesi[oó]n|session|"
    r"vulnerab|cve|owasp|injection|inyecci[oó]n|xss|csrf|ssrf|rce|"
    r"concurren|race-?condition|deadlock|mutex|lock-?free|thread-?safe|hilos|"
    r"distribut|distribuida|consensus|consenso|transaction|transacci[oó]n|"
    r"\bacid\b|isolation|serializab|"
    r"scalab|escalab|throughput|latency|latencia|bottleneck|cuello de botella|"
    r"architecture|arquitectura|design pattern|patr[oó]n de dise[ñn]o|"
    r"microservice|microservicio|monolith|monolito|eventual consistenc|"
    r"migrat|migraci[oó]n|backfill|zero-?downtime|cero downtime|rollback|"
    r"perform|rendimiento|optimi[sz]|complejidad|complexity|big-?o|profiling|"
    r"regex|regular expression|expresi[oó]n regular|"
    r"algorithm|algoritmo|data structure|estructura de datos|\bgraph\b|\btree\b|trie|"
    r"refactor|refactoriza|decouple|acoplamiento|cohesi[oó]n|coupling|cohesion|"
    r"subagent|subagente|multi[- ]?agent|agentic|agentic[- ]?cycle|orquestaci[oó]n|orchestrat|"
    r"prompt[- ]?improv|mejora(?:dor)? de prompt|smart[- ]?trim|compact(?:ion|aci[oó]n)|"
    r"context compact|memory[- ]?bank|banco de memoria|cross[- ]?cli|worker routing|"
    r"fusion|openrouter fusion|deliberation|deliberaci[oó]n|"
    r"production-?ready|listo para producci[oó]n|idiomatic|idiom[aá]tico|"
    r"best practice|mejores pr[aá]cticas"
    r")\b",
    re.IGNORECASE,
)

_HARD_INTENT_SIGNALS = re.compile(
    r"\b(design|architect|review for|audit|analy[sz]e the|assess|evaluate|"
    r"investigate|diagnose|dise[ñn]a|arquitect|audita|analiza|analiz|eval[uú]a|"
    r"investiga|diagnostica|modernize|moderniza|production-?ify|"
    r"make it scalable|make this secure|make our|convert (?:this|the|our|my))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Absolute-target softening patterns
# ---------------------------------------------------------------------------
_ABSOLUTE_REPLACEMENTS = (
    (re.compile(r"(?i)\b100\s?%\s*(?:of\s+)?(?:test\s+)?coverage\b"), "broad test coverage"),
    (re.compile(r"(?i)\b100\s?%\s*de\s+cobertura\b"), "cobertura amplia de pruebas"),
    (re.compile(r"(?i)\b(?:full|complete|total)\s+(?:test\s+)?coverage\b"), "broad test coverage"),
    (
        re.compile(r"(?i)\bcobertura(?:\s+de\s+pruebas)?\s+(?:completa|total)\b"),
        "cobertura amplia de pruebas",
    ),
    (re.compile(r"(?i)\bzero\s+downtime\b"), "minimized downtime"),
    (re.compile(r"(?i)\bcero\s+downtime\b"), "downtime minimizado"),
)
