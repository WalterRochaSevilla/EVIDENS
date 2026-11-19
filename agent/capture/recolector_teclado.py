"""Hook de teclado exclusivo para Packet Tracer con rastreo de origen de portapapeles."""

import ctypes
import ctypes.wintypes
import threading
import time
from typing import Any

import psutil
from pynput import keyboard

from core.configuracion import PACKET_TRACER_PROCESS_KEYWORDS, PALABRAS_ALERTA_VENTANA, PROCESOS_ORIGEN_COPIA_PERMITIDOS, PROCESOS_PROHIBIDOS

_MAPA_NUMPAD_VK: dict[int, str] = {106: "*", 107: "+", 109: "-", 110: ".", 111: "/"}
_TECLAS_EDICION: tuple[str, ...] = ("enter", "backspace", "space", "tab", "up", "down", "left", "right", "delete", "home", "end")


def obtener_hwnd_activo() -> int:
    """Devuelve el identificador (HWND) de la ventana activa."""
    try:
        return int(ctypes.windll.user32.GetForegroundWindow())
    except (AttributeError, OSError):
        return 0


def obtener_titulo_ventana(hwnd: int) -> str:
    """Obtiene el título de la ventana activa en Windows."""
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
    """Devuelve el nombre del ejecutable asociado a la ventana."""
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


def es_proceso_packet_tracer(nombre_proceso: str) -> bool:
    """Verifica si el ejecutable corresponde a Cisco Packet Tracer."""
    return any(k in (nombre_proceso or "").lower() for k in PACKET_TRACER_PROCESS_KEYWORDS)


def es_origen_copia_permitido(proceso_origen: str) -> bool:
    """True si el texto copiado proviene de Packet Tracer o del Bloc de notas permitido."""
    proc = (proceso_origen or "").lower().strip()
    if not proc:
        return True
    return any(p in proc for p in PROCESOS_ORIGEN_COPIA_PERMITIDOS)


def evaluar_alerta_entorno(titulo: str, proceso: str) -> str | None:
    """Detecta si la ventana activa o el proceso corresponden a IA, IDE externo o Task Manager."""
    titulo_min = (titulo or "").lower()
    for palabra in PALABRAS_ALERTA_VENTANA:
        if palabra in titulo_min:
            return palabra.upper()

    proc_min = (proceso or "").lower()
    for proc_prohibido in PROCESOS_PROHIBIDOS:
        if proc_prohibido in proc_min:
            return proc_prohibido.removesuffix(".exe").upper()
    return None


def _traducir_tecla_segura(key: Any) -> str:
    """Traduce teclas incluyendo teclado numérico (Numpad), flechas de edición y filtrando ASCII < 32."""
    vk = getattr(key, "vk", None)
    if isinstance(vk, int):
        if 96 <= vk <= 105:
            return str(vk - 96)
        if vk in _MAPA_NUMPAD_VK:
            return _MAPA_NUMPAD_VK[vk]

    char = getattr(key, "char", None)
    if char == "\x03":
        return "[CTRL+C]"
    if char == "\x16":
        return "[CTRL+V]"
    if char is not None:
        return char if ord(char) >= 32 else ""

    nombre = getattr(key, "name", None)
    if nombre in _TECLAS_EDICION:
        return f"[{nombre}]"
    return ""


class RecolectorTeclado:
    """Captura pulsaciones dentro de Packet Tracer y rastrea el origen de Ctrl+C sin guardar texto externo."""

    def __init__(self) -> None:
        self._listener: keyboard.Listener | None = None
        self._bloqueo = threading.Lock()
        self._eventos: list[dict[str, Any]] = []
        self._pendiente_leer_portapapeles: list[dict[str, Any]] = []
        self._ultimo_origen_copia: dict[str, str] = {"proceso": "", "ventana": ""}
        self._activo = False

    def iniciar(self) -> bool:
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

    def _al_presionar_tecla(self, key: Any) -> None:
        if not self._activo:
            return

        tecla_str = _traducir_tecla_segura(key)
        if not tecla_str:
            return

        hwnd = obtener_hwnd_activo()
        proceso = obtener_proceso_de_ventana(hwnd)
        titulo = obtener_titulo_ventana(hwnd)

        # Rastrear únicamente qué aplicación originó un Ctrl+C (sin registrar teclas ni contraseñas)
        if tecla_str == "[CTRL+C]":
            with self._bloqueo:
                self._ultimo_origen_copia = {"proceso": proceso, "ventana": titulo}

        if not es_proceso_packet_tracer(proceso):
            return

        evento: dict[str, Any] = {
            "timestamp": round(time.time(), 3),
            "ventana": titulo,
            "proceso": proceso,
            "es_packet_tracer": True,
            "tecla": tecla_str,
        }
        with self._bloqueo:
            if tecla_str == "[CTRL+V]":
                evento["origen_copia"] = dict(self._ultimo_origen_copia)
            self._eventos.append(evento)
            if tecla_str in ("[CTRL+C]", "[CTRL+V]"):
                self._pendiente_leer_portapapeles.append(evento)

    def hay_portapapeles_pendiente(self) -> bool:
        with self._bloqueo:
            return bool(self._pendiente_leer_portapapeles)

    def resolver_portapapeles_en_hilo_principal(self, texto_portapapeles: str) -> list[dict[str, str]]:
        """Asigna el portapapeles y devuelve alertas solo si el pegado proviene de origen no permitido."""
        alertas_pegado: list[dict[str, str]] = []
        with self._bloqueo:
            for ev in self._pendiente_leer_portapapeles:
                ev["portapapeles"] = texto_portapapeles
                if ev.get("tecla") == "[CTRL+V]" and texto_portapapeles.strip():
                    origen = ev.get("origen_copia") or {}
                    proc_origen = str(origen.get("proceso", ""))
                    if not es_origen_copia_permitido(proc_origen):
                        alertas_pegado.append({
                            "proceso_origen": proc_origen,
                            "ventana_origen": str(origen.get("ventana", "")),
                            "ventana_destino": str(ev.get("ventana", "")),
                        })
            self._pendiente_leer_portapapeles.clear()
        return alertas_pegado

    def extraer_eventos_nuevos(self) -> list[dict[str, Any]]:
        """Extrae y vacía únicamente los eventos nuevos para anexarlos al archivo .jsonl."""
        with self._bloqueo:
            nuevos = list(self._eventos)
            self._eventos.clear()
            self._pendiente_leer_portapapeles.clear()
            return nuevos
