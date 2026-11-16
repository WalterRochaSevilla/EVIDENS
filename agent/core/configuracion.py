import os
from pathlib import Path

APP_NAME: str = "EVIDENS - Cliente Portable"
APP_VERSION: str = "0.2.0"

DEFAULT_SERVER_URL: str = os.getenv("EVIDENS_SERVER_URL", "http://localhost:8000")
DEFAULT_WS_URL: str = os.getenv("EVIDENS_WS_URL", "ws://localhost:8000")

HEARTBEAT_INTERVAL_SEC: int = 5
WINDOW_WATCH_INTERVAL_SEC: float = 1.0

SYSTEM_ROOT: Path = Path(os.getenv("SystemRoot", "C:\\Windows"))
HOSTS_FILE_PATH: Path = SYSTEM_ROOT / "System32" / "drivers" / "etc" / "hosts"

BASE_AGENT_DIR: Path = Path(__file__).resolve().parent.parent
EVIDENS_DATA_DIR: Path = BASE_AGENT_DIR / "evidencias"
EVIDENS_TEMP_DIR: Path = EVIDENS_DATA_DIR / "logs"
EVIDENS_CLIPS_DIR: Path = EVIDENS_DATA_DIR / "clips"

PACKET_TRACER_PROCESS_KEYWORDS: tuple[str, ...] = ("packettracer", "ciscopt")

PALABRAS_ALERTA_VENTANA: tuple[str, ...] = (
    "deepseek",
    "chatgpt",
    "claude",
    "gemini",
    "perplexity",
    "copilot",
    "openai",
    "stackoverflow",
    "whatsapp",
    "discord",
)

HOSTS_TAG_START: str = "# === INICIO BLOQUEO EVIDENS ==="
HOSTS_TAG_END: str = "# === FIN BLOQUEO EVIDENS ==="

DOMINIOS_BLOQUEO_DEFECTO: list[str] = [
    "deepseek.com",
    "chat.deepseek.com",
    "chatgpt.com",
    "chat.openai.com",
    "openai.com",
    "claude.ai",
    "gemini.google.com",
    "perplexity.ai",
    "copilot.microsoft.com",
    "github.com",
    "stackoverflow.com",
    "discord.com",
    "web.whatsapp.com",
]


def inicializar_directorios_locales() -> None:
    EVIDENS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENS_CLIPS_DIR.mkdir(parents=True, exist_ok=True)