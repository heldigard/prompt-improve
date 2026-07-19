"""prompt-improve — LLM-powered prompt improvement hook for Claude Code."""

__version__ = "17.2.0"

# Bootstrap sys.path for harness helpers (ollama_client, cheap_llm).
from prompt_improve.shared import compat as _compat  # noqa: F401
