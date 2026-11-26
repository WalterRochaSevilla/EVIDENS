"""Hook de teclado para Packet Tracer, origen de portapapeles y detector de intención en RAM."""

import ctypes
import ctypes.wintypes
import threading
import time
from typing import Any

import psutil
from pynput import keyboard

from capture.detector_intencion import DetectorIntencionRAM, evaluar_intencion_en_titulo
from core.configuracion import PACKET_TRACER_PROCESS_KEYWORDS, PALABRAS_ALERTA_VENTANA, PROCESOS_ORIGEN_COPIA_PERMITIDOS, PROCESOS_PROHIBIDOS

_MAPA_NUMPAD_VK: dict[int, str] = {106: "*", 107: "+", 109: "-", 110: ".", 111: "/"}
_TECLAS_EDICION: tuple[str, ...] = ("enter", "backspace", "space", "tab", "up", "down", "left", "right", "delete", "home", "end")
_VENTANAS_LOGIN_IGNORAR: tuple[str, ...] = ("login", "sign in", "iniciar sesión", "iniciar sesion", "skills for all", "networking academy", "netacad", "cisco account")


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
        return psutil.Process(pid.value).name().lower() if pid.value else ""
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError, OSError):
        return ""


def es_proceso_packet_tracer(nombre_proceso: str) -> bool:
    return any(k in (nombre_proceso or "").lower() for k in PACKET_TRACER_PROCESS_KEYWORDS)


def es_ventana_login_privada(titulo: str) -> bool:
    """Evita registrar credenciales si el estudiante inicia sesión en Cisco NetAcad / Skills for All."""
    t_min = (titulo or "").lower()
    return any(clave in t_min for clave in _VENTANAS_LOGIN_IGNORAR)


def es_origen_copia_permitido(proceso_origen: str) -> bool:
    proc = (proceso_origen or "").lower().strip()
    return not proc or any(p in proc for p in PROCESOS_ORIGEN_COPIA_PERMITIDOS)


def evaluar_alerta_entorno(titulo: str, proceso: str) -> str | None:
    """Evalúa IA conocida, procesos prohibidos o búsquedas de redes/Modo IA en navegador."""
    titulo_min = (titulo or "").lower()
    for palabra in PALABRAS_ALERTA_VENTANA:
        if palabra in titulo_min:
            return palabra.upper()

    proc_min = (proceso or "").lower()
    for proc_prohibido in PROCESOS_PROHIBIDOS:
        if proc_prohibido in proc_min:
            return proc_prohibido.removesuffix(".exe").upper()

    return evaluar_intencion_en_titulo(titulo, proceso)


def _traducir_tecla_segura(key: Any) -> str:
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
    return f"[{nombre}]" if nombre in _TECLAS_EDICION else ""


class RecolectorTeclado:
    """Registra CLI en Packet Tracer, rastrea origen de Ctrl+C y evalúa intención en RAM."""

    def __init__(self) -> None:
        self._listener: keyboard.Listener | None = None
        self._bloqueo = threading.Lock()
        self._eventos: list[dict[str, Any]] = []
        self._pendiente_leer_portapapeles: list[dict[str, Any]] = []
        self._ultimo_origen_copia: dict[str, str] = {"proceso": "", "ventana": ""}
        self._detector_intencion = DetectorIntencionRAM()
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

        if tecla_str == "[CTRL+C]":
            with self._bloqueo:
                self._ultimo_origen_copia = {"proceso": proceso, "ventana": titulo}

        if not es_proceso_packet_tracer(proceso):
            # Fuera de Packet Tracer: analizar intención solo en RAM volátil (jamás guardar en disco)
            self._detector_intencion.analizar_tecla(proceso, titulo, tecla_str)
            return

        if es_ventana_login_privada(titulo):
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

    def extraer_alertas_intencion_ram(self) -> list[dict[str, Any]]:
        """Devuelve alertas disparadas por el detector de intención en RAM."""
        return self._detector_intencion.extraer_alertas()

    def resolver_portapapeles_en_hilo_principal(self, texto_portapapeles: str) -> list[dict[str, str]]:
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
        with self._bloqueo:
            nuevos = list(self._eventos)
            self._eventos.clear()
            self._pendiente_leer_portapapeles.clear()
            return nuevos
