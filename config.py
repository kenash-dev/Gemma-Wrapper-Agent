import os


GEMMA_BASE_URL = os.environ.get("GEMMA_BASE_URL", "http://localhost:11434/v1")
GEMMA_MODEL = os.environ.get("GEMMA_MODEL", "gemma2:27b")
AGENT_MAX_ITERATIONS = int(os.environ.get("AGENT_MAX_ITERATIONS", "15"))
AGENT_WORKSPACE = os.path.abspath(os.environ.get("AGENT_WORKSPACE", "."))
AGENT_CONFIRM_WRITES = os.environ.get("AGENT_CONFIRM_WRITES", "true").lower() == "true"
AGENT_TEMPERATURE = float(os.environ.get("AGENT_TEMPERATURE", "0.1"))
AGENT_MAX_TOKENS = int(os.environ.get("AGENT_MAX_TOKENS", "2048"))
AGENT_CONTEXT_BUDGET = int(os.environ.get("AGENT_CONTEXT_BUDGET", "6000"))
