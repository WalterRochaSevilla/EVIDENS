"""Configuración, constantes y rutas locales para el agente portable EVIDENS."""

import os
from pathlib import Path

APP_NAME: str = "EVIDENS - Cliente Portable"
APP_VERSION: str = "0.1.0"

DEFAULT_SERVER_URL: str = os.getenv("EVIDENS_SERVER_URL", "http://localhost:8000")
DEFAULT_WS_URL: str = os.getenv("EVIDENS_WS_URL", "ws://localhost:8000")

HEARTBEAT_INTERVAL_SEC: int = 5
POLLING_INTERVAL_SEC: int = 3
KEYLOGGER_FLUSH_INTERVAL_SEC: int = 10

SYSTEM_ROOT: Path = Path(os.getenv("SystemRoot", "C:\\Windows"))
HOSTS_FILE_PATH: Path = SYSTEM_ROOT / "System32" / "drivers" / "etc" / "hosts"

LOCAL_APPDATA: Path = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
EVIDENS_DATA_DIR: Path = LOCAL_APPDATA / "EVIDENS"
EVIDENS_TEMP_DIR: Path = EVIDENS_DATA_DIR / "temp"
EVIDENS_EVIDENCE_DIR: Path = EVIDENS_DATA_DIR / "evidence"

PACKET_TRACER_PROCESS_KEYWORDS: list[str] = ["packettracer", "ciscopt"]

HOSTS_TAG_START: str = "# === INICIO BLOQUEO EVIDENS ==="
HOSTS_TAG_END: str = "# === FIN BLOQUEO EVIDENS ==="

DOMINIOS_BLOQUEO_DEFECTO: list[str] = [
    "chatgpt.com",
    "openai.com",
    "claude.ai",
    "gemini.google.com",
    "github.com",
    "stackoverflow.com",
    "discord.com",
    "web.whatsapp.com",
]


def inicializar_directorios_locales() -> None:
    EVIDENS_DATA_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENS_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENS_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)