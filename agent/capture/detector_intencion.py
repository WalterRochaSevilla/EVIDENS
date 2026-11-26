"""Detector de intenciones en RAM volátil (Google Modo IA, prompts y búsquedas de redes)."""

import re
import threading
import time
from typing import Any

PROCESOS_NAVEGADOR: tuple[str, ...] = (
    "brave.exe",
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "opera.exe",
    "vivaldi.exe",
    "arc.exe",
)

# Patrones estructurales de prompt o consulta técnica de redes (evaluados solo en RAM)
_PATRONES_INTENCION: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PROMPT_VLSM_SUBNETEO", re.compile(r"\b(vlsm|subnete[oa]|subnetting|subredes|mascara\s+de\s+subred|cidr)\b", re.I)),
    ("PROMPT_COMANDOS_CISCO", re.compile(r"\b(packet\s*tracer|cisco\s*ios|router\s+(rip|ospf|eigrp|bgp)|ip\s+route|ip\s+address|ip\s+dhcp|dhcp\s+pool|default-router|configure\s+terminal|switchport|encapsulation\s+dot1q|dot1q|vtp\s+mode|etherchannel|channel-group|port-channel|vlan\s+\d+|hwic-2t)\b", re.I)),
    ("PROMPT_SOLICITUD_IA", re.compile(r"\b(haz(me)?\s+(un|una|el)|calcula(me)?|resuelve(me)?|dame\s+los\s+comandos|como\s+configur(ar|o)|configurar\s+(router|switch|red|ospf|rip|vlan|vtp|dhcp|etherchannel)|explica(me)?\s+(vlsm|subnet|ospf|rip|vtp|vlan|etherchannel))\b", re.I)),
    ("DIRECCIONAMIENTO_EN_BUSQUEDA", re.compile(r"(192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|255\.255\.\d+\.\d+)")),
    ("MODO_IA_NAVEGADOR", re.compile(r"\b(modo\s+ia|ai\s+mode|ai\s+overview|vision\s+general\s+creada\s+por\s+ia)\b", re.I)),
)


def es_navegador(nombre_proceso: str) -> bool:
    """Indica si el ejecutable corresponde a un navegador web."""
    proc = (nombre_proceso or "").lower()
    return any(nav in proc for nav in PROCESOS_NAVEGADOR)


def _normalizar_acentos(texto: str) -> str:
    reemplazos = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return (texto or "").translate(reemplazos)


def evaluar_intencion_en_titulo(titulo: str, proceso: str) -> str | None:
    """Detecta consultas de redes o Modo IA directamente en el título de la pestaña del navegador."""
    if not es_navegador(proceso) or not titulo:
        return None
    limpio = _normalizar_acentos(titulo)
    for categoria, patron in _PATRONES_INTENCION:
        if patron.search(limpio):
            return categoria
    return None


class DetectorIntencionRAM:
    """Analiza en RAM volátil las teclas en navegadores/apps externas sin guardar texto en disco."""

    def __init__(self, ttl_segundos: float = 12.0, max_caracteres: int = 180) -> None:
        self._bloqueo = threading.Lock()
        self._buffer: list[str] = []
        self._ultima_ventana: str = ""
        self._ultimo_ts: float = 0.0
        self._ultimo_disparo_ts: float = 0.0
        self._ttl = ttl_segundos
        self._max_caracteres = max_caracteres
        self._alertas_pendientes: list[dict[str, Any]] = []

    def analizar_tecla(self, proceso: str, titulo: str, tecla: str) -> None:
        """Evalúa patrones de intención sobre un búfer efímero en RAM (nunca se persiste)."""
        if not es_navegador(proceso):
            return

        ahora = time.time()
        with self._bloqueo:
            if (ahora - self._ultimo_ts) > self._ttl or titulo != self._ultima_ventana:
                self._buffer.clear()
                self._ultima_ventana = titulo
            self._ultimo_ts = ahora

            if tecla == "[backspace]":
                if self._buffer:
                    self._buffer.pop()
                return
            if tecla in ("[space]", "[tab]"):
                self._buffer.append(" ")
            elif tecla == "[enter]":
                self._evaluar_buffer_locked(proceso, titulo, ahora)
                self._buffer.clear()
                return
            elif len(tecla) == 1:
                self._buffer.append(tecla)
            else:
                return

            if len(self._buffer) > self._max_caracteres:
                self._buffer = self._buffer[-self._max_caracteres:]

            self._evaluar_buffer_locked(proceso, titulo, ahora)

    def _evaluar_buffer_locked(self, proceso: str, titulo: str, ahora: float) -> None:
        if (ahora - self._ultimo_disparo_ts) < 5.0:
            return
        texto = _normalizar_acentos("".join(self._buffer))
        for categoria, patron in _PATRONES_INTENCION:
            if patron.search(texto):
                self._ultimo_disparo_ts = ahora
                # Descartar el texto en RAM de inmediato para preservar la privacidad
                self._buffer.clear()
                self._alertas_pendientes.append({
                    "categoria": categoria,
                    "ventana": titulo or "Navegador",
                    "proceso": proceso,
                })
                return

    def extraer_alertas(self) -> list[dict[str, Any]]:
        """Extrae las alertas de intención detectadas para que el hilo principal vuelque el clip."""
        with self._bloqueo:
            copia = list(self._alertas_pendientes)
            self._alertas_pendientes.clear()
            return copia
