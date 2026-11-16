import ctypes
import threading
import time
from typing import Any

import psutil

try:
    from pynput import keyboard
    PYNPUT_DISPONIBLE = True
except ImportError:
    keyboard = None
    PYNPUT_DISPONIBLE = False

from core.configuracion import PACKET_TRACER_PROCESS_KEYWORDS


def obtener_hwnd_activo() -> int:
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except (AttributeError, OSError):
        return 0


def obtener_titulo_ventana(hwnd: int) -> str:
    if not hwnd:
        return ""
    try:
        user32 = ctypes.windll.user32
        longitud = user32.GetWindowTextLengthW(hwnd)
        if longitud == 0:
            return ""
        buffer = ctypes.create_unicode_buffer(longitud + 1)
        user32.GetWindowTextW(hwnd, buffer, longitud + 1)
        return buffer.value
    except (AttributeError, OSError):
        return ""


def obtener_proceso_de_ventana(hwnd: int) -> str:
    if not hwnd:
        return ""
    try:
        pid = ctypes.wintypes.DWORD()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        return psutil.Process(pid.value).name().lower()
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, OSError):
        return ""


def _es_proceso_pt(nombre_proceso: str) -> bool:
    if not nombre_proceso:
        return False
    return any(clave in nombre_proceso for clave in PACKET_TRACER_PROCESS_KEYWORDS)


class RecolectorTeclado:
    """Captura pulsaciones asociadas a la ventana activa, filtrando por proceso."""

    def __init__(self, solo_ventanas_pt: bool = True) -> None:
        self._listener: Any = None
        self._bloqueo = threading.Lock()
        self._eventos: list[dict[str, Any]] = []
        self._activo = False
        self.solo_ventanas_pt = solo_ventanas_pt
        self._cache_hwnd: int = 0
        self._cache_es_pt: bool = False
        self._cache_titulo: str = ""

    @property
    def activo(self) -> bool:
        return self._activo

    def _es_ventana_de_interes(self, hwnd: int) -> bool:
        if not self.solo_ventanas_pt:
            return True
        if not hwnd:
            return False
        if hwnd == self._cache_hwnd:
            return self._cache_es_pt
        # Refrescar caché
        nombre_proceso = obtener_proceso_de_ventana(hwnd)
        self._cache_hwnd = hwnd
        self._cache_es_pt = _es_proceso_pt(nombre_proceso)
        self._cache_titulo = obtener_titulo_ventana(hwnd)
        return self._cache_es_pt

    def _al_presionar_tecla(self, key: Any) -> None:
        if not self._activo:
            return

        hwnd = obtener_hwnd_activo()
        if not self._es_ventana_de_interes(hwnd):
            return
        titulo = self._cache_titulo if hwnd == self._cache_hwnd else obtener_titulo_ventana(hwnd)

        try:
            if hasattr(key, "char") and key.char is not None:
                caracter = key.char
            else:
                caracter = f"[{key.name}]"
        except (AttributeError, ValueError):
            caracter = str(key)

        evento = {
            "timestamp": time.time(),
            "ventana": titulo,
            "tecla": caracter,
            "tipo": "press",
        }

        with self._bloqueo:
            self._eventos.append(evento)

    def iniciar(self) -> bool:
        if not PYNPUT_DISPONIBLE:
            return False
        if self._activo:
            return True
        self._activo = True
        self._listener = keyboard.Listener(on_press=self._al_presionar_tecla)
        self._listener.daemon = True
        self._listener.start()
        return True

    def detener(self) -> None:
        self._activo = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def extraer_eventos(self) -> list[dict[str, Any]]:
        with self._bloqueo:
            eventos_copia = list(self._eventos)
            self._eventos.clear()
            return eventos_copia

    def obtener_total_eventos(self) -> int:
        with self._bloqueo:
            return len(self._eventos)