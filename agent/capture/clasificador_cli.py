import re
from typing import Any

PATRON_VENTANA_DISPOSITIVO = re.compile(
    r"^\s*((?:Multilayer Switch|Router|Switch|Server|Laptop|PC)\d*)"
    r"(?:\s*-\s*(?:CLI|Command Prompt|Desktop))?\s*$",
    re.IGNORECASE,
)

PATRON_COMANDO_HOSTNAME = re.compile(r"^\s*hostname\s+([A-Za-z0-9_\-\.]+)\s*$", re.IGNORECASE)


def extraer_dispositivo_de_ventana(titulo_ventana: str) -> str | None:
    if not titulo_ventana:
        return None
    coincidencia = PATRON_VENTANA_DISPOSITIVO.match(titulo_ventana.strip())
    return coincidencia.group(1) if coincidencia else None


def extraer_nuevo_hostname(comando: str) -> str | None:
    coincidencia = PATRON_COMANDO_HOSTNAME.match(comando)
    return coincidencia.group(1) if coincidencia else None


def _aplicar_tecla_a_buffer(buffer_actual: list[str], tecla: str) -> bool:
    if tecla == "[enter]":
        return True
    if tecla == "[backspace]":
        if buffer_actual:
            buffer_actual.pop()
        return False
    if tecla == "[space]":
        buffer_actual.append(" ")
        return False
    if tecla and not tecla.startswith("["):
        buffer_actual.append(tecla)
    return False


def reconstruir_lineas_por_ventana(eventos: list[dict[str, Any]]) -> list[tuple[str, str]]:
    buffers_por_ventana: dict[str, list[str]] = {}
    lineas_completas: list[tuple[str, str]] = []

    for evento in sorted(eventos, key=lambda ev: ev.get("timestamp", 0.0)):
        ventana = str(evento.get("ventana", "")).strip() or "SIN_VENTANA"
        buffer_ventana = buffers_por_ventana.setdefault(ventana, [])
        if _aplicar_tecla_a_buffer(buffer_ventana, str(evento.get("tecla", ""))):
            linea = "".join(buffer_ventana).strip()
            buffer_ventana.clear()
            if linea:
                lineas_completas.append((ventana, linea))
    return lineas_completas


def agrupar_evidencia_por_dispositivo(eventos: list[dict[str, Any]]) -> dict[str, Any]:
    comandos_por_nodo: dict[str, list[str]] = {}
    alias_hostname: dict[str, str] = {}
    actividad_externa: list[dict[str, str]] = []

    for ventana, comando in reconstruir_lineas_por_ventana(eventos):
        nodo_fisico = extraer_dispositivo_de_ventana(ventana)
        if not nodo_fisico:
            actividad_externa.append({"ventana": ventana, "texto": comando})
            continue
        comandos_por_nodo.setdefault(nodo_fisico, []).append(comando)
        nuevo_alias = extraer_nuevo_hostname(comando)
        if nuevo_alias:
            alias_hostname[nodo_fisico] = nuevo_alias

    dispositivos_formateados = {
        f"{nodo} ({alias_hostname[nodo]})" if nodo in alias_hostname else nodo: lista
        for nodo, lista in comandos_por_nodo.items()
    }
    return {
        "alias_detectados": alias_hostname,
        "dispositivos": dispositivos_formateados,
        "otras_ventanas": actividad_externa,
    }