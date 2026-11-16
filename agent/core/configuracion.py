"""Configuración, selección segura de disco fijo y constantes del cliente portable EVIDENS."""

import hashlib
import os
import tempfile
from pathlib import Path

import psutil

APP_NAME: str = "EVIDENS - Cliente Portable"
APP_VERSION: str = "0.4.1"

# Hash SHA-256 de la clave docente por defecto (sin exponer el PIN en texto plano en el binario)
_PIN_DOCENTE_SHA256: str = "158a323a7ba44870f23d96f1516dd70aa48e9a72db4ebb026b0a89e212a208ab"

DEFAULT_SERVER_URL: str = os.getenv("EVIDENS_SERVER_URL", "http://localhost:8000")
DEFAULT_WS_URL: str = os.getenv("EVIDENS_WS_URL", "ws://localhost:8000")

CHECKPOINT_INTERVAL_SEC: int = 3
SERVER_POLL_INTERVAL_SEC: int = 5
BUFFER_VIDEO_SECONDS: int = 20

SYSTEM_ROOT: Path = Path(os.getenv("SystemRoot", "C:\\Windows"))
HOSTS_FILE_PATH: Path = SYSTEM_ROOT / "System32" / "drivers" / "etc" / "hosts"

HOSTS_TAG_START: str = "# === INICIO BLOQUEO EVIDENS ==="
HOSTS_TAG_END: str = "# === FIN BLOQUEO EVIDENS ==="

PACKET_TRACER_PROCESS_KEYWORDS: tuple[str, ...] = ("packettracer", "ciscopt")
PROCESOS_PROHIBIDOS: tuple[str, ...] = ("taskmgr.exe", "processhacker.exe", "procexp.exe")

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
    "administrador de tareas",
    "task manager",
)

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


def verificar_pin_docente(pin_ingresado: str | None) -> bool:
    """Valida la clave docente contra variable de entorno o hash SHA-256 sin exponerla en código."""
    if not pin_ingresado:
        return False
    limpio = pin_ingresado.strip()
    pin_env = os.getenv("EVIDENS_PIN_DOCENTE", "").strip()
    if pin_env:
        return limpio == pin_env
    digest = hashlib.sha256(limpio.encode("utf-8")).hexdigest()
    return digest == _PIN_DOCENTE_SHA256


def _es_disco_fijo(letra_unidad: str) -> bool:
    """Verifica con psutil que la unidad sea un disco fijo y no un USB o lector óptico."""
    prefijo = letra_unidad.upper().rstrip("\\/")
    try:
        for part in psutil.disk_partitions(all=False):
            disp = part.device.upper().rstrip("\\/")
            opts = part.opts.lower()
            if disp == prefijo:
                return "fixed" in opts and "removable" not in opts and "cdrom" not in opts
    except Exception:
        pass
    return False


def obtener_directorio_base_evidencias() -> Path:
    """Prioriza D:\\ solo si es un disco fijo escribible; si no, usa el Escritorio."""
    candidatos: list[Path] = []
    if _es_disco_fijo("D:"):
        candidatos.append(Path("D:/EVIDENS_Evidencias"))

    for nombre_esc in ("Desktop", "Escritorio"):
        esc = Path.home() / nombre_esc
        if esc.exists():
            candidatos.append(esc / "EVIDENS_Evidencias")
            break

    candidatos.append(Path.home() / "EVIDENS_Evidencias")
    candidatos.append(Path(tempfile.gettempdir()) / "EVIDENS_Evidencias")

    for ruta in candidatos:
        try:
            ruta.mkdir(parents=True, exist_ok=True)
            return ruta
        except OSError:
            continue
    return Path(".")


def obtener_archivo_sesion_activa() -> Path:
    """Devuelve la ruta del archivo de estado de sesión activa."""
    return obtener_directorio_base_evidencias() / "sesion_en_curso.json"
