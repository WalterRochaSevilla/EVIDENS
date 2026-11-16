import ctypes
import ctypes.wintypes
import threading
import time
from typing import Any, Callable

import psutil
from pynput import keyboard

from core.configuracion import (
    PACKET_TRACER_PROCESS_KEYWORDS,
    PALABRAS_ALERTA_VENTANA,
    WINDOW_WATCH_INTERVAL_SEC,
)

CF_UNICODETEXT = 13


def obtener_hwnd_activo() -> int:
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except (AttributeError, OSError):
        return 0


def obtener_titulo_ventana(hwnd: int) -> str:
    if not hwnd:
        return ""
    try:
        longitud = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if longitud <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(longitud + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buffer, longitud + 1)
        return buffer.value.strip()
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


def leer_portapapeles_windows() -> str:
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    if not user32.OpenClipboard(0):
        return ""
    try:
        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        kernel32.GlobalLock.restype = ctypes.c_wchar_p
        texto = kernel32.GlobalLock(handle)
        contenido = str(texto) if texto else ""
        kernel32.GlobalUnlock(handle)
        return contenido.strip()
    except (AttributeError, OSError):
        return ""
    finally:
        user32.CloseClipboard()


def es_proceso_packet_tracer(nombre_proceso: str) -> bool:
    return any(clave in nombre_proceso.lower() for clave in PACKET_TRACER_PROCESS_KEYWORDS)


def detectar_alerta_en_titulo(titulo: str) -> str | None:
    """Devuelve el término prohibido si el título de ventana contiene IA o sitios restringidos."""
    titulo_min = titulo.lower()
    for palabra in PALABRAS_ALERTA_VENTANA:
        if palabra in titulo_min:
            return palabra.upper()
    return None


def _traducir_tecla(key: Any) -> tuple[str, str]:
    char = getattr(key, "char", None)
    if char == "\x03":
        return "[CTRL+C]", leer_portapapeles_windows()
    if char == "\x16":
        return "[CTRL+V]", leer_portapapeles_windows()
    if char is not None and ord(char) >= 32:
        return char, ""
    nombre = getattr(key, "name", None)
    return (f"[{nombre}]" if nombre else str(key)), ""


class RecolectorTeclado:

    def __init__(self, al_detectar_alerta: Callable[[str, str], None] | None = None) -> None:
        self._listener: keyboard.Listener | None = None
        self._hilo_ventana: threading.Thread | None = None
        self._bloqueo = threading.Lock()
        self._eventos: list[dict[str, Any]] = []
        self._alertas_ventana: list[dict[str, Any]] = []
        self._activo = False
        self._ultimo_titulo_alerta = ""
        self.al_detectar_alerta = al_detectar_alerta

    def iniciar(self) -> bool:
        if self._activo:
            return True
        self._activo = True
        self._listener = keyboard.Listener(on_press=self._al_presionar_tecla)
        self._listener.daemon = True
        self._listener.start()

        self._hilo_ventana = threading.Thread(target=self._vigilar_ventana_activa, daemon=True)
        self._hilo_ventana.start()
        return True

    def detener(self) -> None:
        self._activo = False
        if self._listener is not None:
            self._listener.stop()
            self._listener = None

    def _vigilar_ventana_activa(self) -> None:
        while self._activo:
            hwnd = obtener_hwnd_activo()
            titulo = obtener_titulo_ventana(hwnd)
            termino = detectar_alerta_en_titulo(titulo)
            if termino and titulo != self._ultimo_titulo_alerta:
                self._ultimo_titulo_alerta = titulo
                alerta = {
                    "timestamp": round(time.time(), 2),
                    "termino_detectado": termino,
                    "ventana": titulo,
                    "proceso": obtener_proceso_de_ventana(hwnd),
                }
                with self._bloqueo:
                    self._alertas_ventana.append(alerta)
                if self.al_detectar_alerta:
                    self.al_detectar_alerta(termino, titulo)
            elif not termino:
                self._ultimo_titulo_alerta = ""
            time.sleep(WINDOW_WATCH_INTERVAL_SEC)

    def _al_presionar_tecla(self, key: Any) -> None:
        if not self._activo:
            return
        hwnd = obtener_hwnd_activo()
        titulo = obtener_titulo_ventana(hwnd)
        proceso = obtener_proceso_de_ventana(hwnd)
        tecla_str, texto_portapapeles = _traducir_tecla(key)

        evento: dict[str, Any] = {
            "timestamp": round(time.time(), 3),
            "ventana": titulo,
            "proceso": proceso,
            "es_packet_tracer": es_proceso_packet_tracer(proceso),
            "tecla": tecla_str,
        }
        if texto_portapapeles:
            evento["portapapeles"] = texto_portapapeles

        with self._bloqueo:
            self._eventos.append(evento)

    def extraer_datos(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        with self._bloqueo:
            ev_copia = list(self._eventos)
            al_copia = list(self._alertas_ventana)
            self._eventos.clear()
            self._alertas_ventana.clear()
            return ev_copia, al_copia