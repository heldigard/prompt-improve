"""prompt-improve — target-aware prompt improvement hook for agentic CLIs."""

__version__ = "17.3.0"

# Bootstrap sys.path for harness helpers (ollama_client, cheap_llm).
from prompt_improve.shared import compat as _compat  # noqa: F401
