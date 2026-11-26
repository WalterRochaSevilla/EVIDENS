"""Configuración, selección segura de disco fijo y constantes del cliente portable EVIDENS."""

import hashlib
import os
import sys
import tempfile
from pathlib import Path

import psutil

APP_NAME: str = "EVIDENS - Cliente de Examen"
APP_VERSION: str = "0.6.0"
APP_USER_MODEL_ID: str = "UCB.EVIDENS.ClienteExamen.1.0"

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

# Solo se permite copiar/pegar entre ventanas del propio Packet Tracer (Bloc de notas genera alerta)
PROCESOS_ORIGEN_COPIA_PERMITIDOS: tuple[str, ...] = ("packettracer", "ciscopt")

PROCESOS_PROHIBIDOS: tuple[str, ...] = (
    "taskmgr.exe",
    "processhacker.exe",
    "procexp.exe",
    "antigravity.exe",
    "cursor.exe",
    "windsurf.exe",
    "code.exe",
    "notepad.exe",
    "notepad++.exe",
    "wordpad.exe",
    "winword.exe",
)

PALABRAS_ALERTA_VENTANA: tuple[str, ...] = (
    "antigravity",
    "cursor",
    "windsurf",
    "visual studio code",
    "bloc de notas",
    "notepad",
    "deepseek",
    "chatgpt",
    "claude",
    "gemini",
    "perplexity",
    "copilot",
    "openai",
    "grok",
    "poe",
    "mistral",
    "blackbox",
    "phind",
    "notebooklm",
    "stackoverflow",
    "whatsapp",
    "telegram",
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
    "grok.com",
    "poe.com",
    "github.com",
    "stackoverflow.com",
    "discord.com",
    "web.whatsapp.com",
    "web.telegram.org",
]


def _obtener_recurso_asset(nombre_archivo: str) -> Path | None:
    """Localiza un recurso en agent/assets/ tanto en fuente como empaquetado en PyInstaller."""
    base_pyinstaller = getattr(sys, "_MEIPASS", None)
    if base_pyinstaller:
        candidato = Path(base_pyinstaller) / "assets" / nombre_archivo
        if candidato.exists():
            return candidato
    candidato_local = Path(__file__).resolve().parent.parent / "assets" / nombre_archivo
    return candidato_local if candidato_local.exists() else None


def obtener_ruta_icono() -> Path | None:
    return _obtener_recurso_asset("evidens.ico")


def obtener_ruta_plantilla_pkt() -> Path | None:
    """Retorna la ruta de assets/plantilla_vacia.pkt si existe como plantilla base."""
    return _obtener_recurso_asset("plantilla_vacia.pkt")


def verificar_pin_docente(pin_ingresado: str | None) -> bool:
    if not pin_ingresado:
        return False
    limpio = pin_ingresado.strip()
    pin_env = os.getenv("EVIDENS_PIN_DOCENTE", "").strip()
    if pin_env:
        return limpio == pin_env
    return hashlib.sha256(limpio.encode("utf-8")).hexdigest() == _PIN_DOCENTE_SHA256


def _es_disco_fijo(letra_unidad: str) -> bool:
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
    return obtener_directorio_base_evidencias() / "sesion_en_curso.json"
