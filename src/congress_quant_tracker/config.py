"""Application configuration loaded from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

_THIS_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd()
BASE_DIR = _THIS_FILE.parent.parent.parent if "__file__" in globals() else Path.cwd()

# override=True so .env wins over empty/stale shell env vars
load_dotenv(BASE_DIR / ".env", override=True)


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR}/congress_quant_tracker.db",
    )
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_BASE_URL: str | None = os.getenv("ANTHROPIC_BASE_URL") or None
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

    # Groq (fast OpenAI-compatible LLM for PTR extraction & Copilot)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Local OpenAI-compatible Llama server
    LOCAL_LLM_URL: str = os.getenv("LOCAL_LLM_URL", "http://127.0.0.1:8080/v1")

    # Tavily (search / ticker resolve / news filters)
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

    CONGRESSINVESTS_API: str = os.getenv(
        "CONGRESSINVESTS_API",
        "https://congressinfor-production.up.railway.app",
    )

    DATA_DIR: Path = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
    PDF_DOWNLOAD_DIR: Path = Path(os.getenv("PDF_DOWNLOAD_DIR", DATA_DIR / "pdfs"))

    MAX_PDF_PAGES: int = int(os.getenv("MAX_PDF_PAGES", "200"))
    FETCH_TIMEOUT_SECONDS: int = int(os.getenv("FETCH_TIMEOUT_SECONDS", "120"))
    PARSE_BATCH_SIZE: int = int(os.getenv("PARSE_BATCH_SIZE", "10"))

    NO_YF: bool = os.getenv("NO_YF", "0") == "1"
    # Market prices / charts (can stay on even if NO_YF=1 for scorer)
    MARKET_DATA_ENABLED: bool = os.getenv("MARKET_DATA_ENABLED", "1") == "1"
    # When true, always call Groq even if regex already found trades
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "0") == "1"

    # Optional HTTP(S) proxy for Senate eFD (must support CONNECT/HTTPS)
    # Example: http://15.204.205.208:7777
    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "") or os.getenv("HTTPS_PROXY", "")

    DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

    # Automatic background data sync on server startup
    AUTO_SYNC_ON_STARTUP: bool = os.getenv("AUTO_SYNC_ON_STARTUP", "1") == "1"
    STARTUP_SYNC_DAYS: int = int(os.getenv("STARTUP_SYNC_DAYS", "90"))
    STARTUP_SYNC_MAX: int = int(os.getenv("STARTUP_SYNC_MAX", "60"))

    # API bind address (127.0.0.1 = local only; use 0.0.0.0 to expose on LAN)
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    def ensure_dirs(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.PDF_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
