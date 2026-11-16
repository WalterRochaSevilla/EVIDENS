"""Clasificación de actividad CLI en Cisco Packet Tracer por nodo y alias de hostname."""

import re
from typing import Any

PATRON_VENTANA_DISPOSITIVO = re.compile(
    r"^\s*((?:Multilayer Switch|Router|Switch|Server|Laptop|PC)\s*\d*(?:\(\d+\))?)"
    r"(?:\s*-\s*.*)?$",
    re.IGNORECASE,
)

PATRON_COMANDO_HOSTNAME = re.compile(
    r"^\s*host(?:name)?\s+([A-Za-z0-9_\-\.]+)\s*$", re.IGNORECASE
)

_VENTANAS_DIALOGO_IGNORAR = (
    "save file",
    "open file",
    "guardar",
    "abrir",
    "print",
    "preferences",
    "options",
)


def identificar_nodo_pt(titulo_ventana: str, es_pt: bool) -> str | None:
    """Identifica el nodo solo si el proceso es Packet Tracer; ignora cuadros de diálogo."""
    if not es_pt:
        return None
    limpio = (titulo_ventana or "").strip()
    if not limpio:
        return None
    limpio_min = limpio.lower()
    if any(limpio_min.startswith(d) for d in _VENTANAS_DIALOGO_IGNORAR):
        return None
    if limpio_min.startswith("cisco packet tracer"):
        return "Topología"
    coincidencia = PATRON_VENTANA_DISPOSITIVO.match(limpio)
    if coincidencia:
        return coincidencia.group(1).strip()
    return limpio


def extraer_nuevo_hostname(comando: str) -> str | None:
    """Detecta si el comando ejecutado asigna un nuevo hostname en IOS (hostname o host)."""
    coincidencia = PATRON_COMANDO_HOSTNAME.match(comando.strip())
    return coincidencia.group(1) if coincidencia else None


def _procesar_pegado(
    evento: dict[str, Any],
    lineas_salida: list[tuple[str, bool, str]],
    eventos_portapapeles: list[dict[str, Any]],
) -> None:
    tecla = str(evento.get("tecla", ""))
    texto_clip = str(evento.get("portapapeles", "")).strip()
    ventana = str(evento.get("ventana", "")) or "SIN_VENTANA"
    es_pt = bool(evento.get("es_packet_tracer", False))

    contenido_desc = texto_clip[:300] if texto_clip else "[Objeto de topología en Packet Tracer]"
    eventos_portapapeles.append({
        "accion": tecla,
        "ventana": ventana,
        "contenido": contenido_desc,
    })
    if tecla == "[CTRL+V]" and texto_clip:
        for linea_pegada in texto_clip.splitlines():
            if linea_pegada.strip():
                lineas_salida.append((ventana, es_pt, f"[PEGADO] {linea_pegada.strip()}"))


def _aplicar_tecla_normal(buffer_actual: list[str], tecla: str) -> bool:
    if tecla == "[enter]":
        return True
    if tecla == "[backspace]":
        if buffer_actual:
            buffer_actual.pop()
    elif tecla in ("[space]", "[tab]"):
        if not buffer_actual or buffer_actual[-1] != " ":
            buffer_actual.append(" ")
    elif tecla and not tecla.startswith("["):
        buffer_actual.append(tecla)
    return False


def reconstruir_actividad(
    eventos: list[dict[str, Any]],
) -> tuple[list[tuple[str, bool, str]], list[dict[str, Any]]]:
    """Reconstruye las líneas de comando tecleadas por ventana a partir del flujo de eventos."""
    buffers: dict[str, tuple[bool, list[str]]] = {}
    lineas: list[tuple[str, bool, str]] = []
    portapapeles_log: list[dict[str, Any]] = []

    for ev in sorted(eventos, key=lambda x: x.get("timestamp", 0.0)):
        ventana = str(ev.get("ventana", "")).strip() or "SIN_VENTANA"
        es_pt = bool(ev.get("es_packet_tracer", False))
        tecla = str(ev.get("tecla", ""))

        if tecla in ("[CTRL+C]", "[CTRL+V]"):
            _procesar_pegado(ev, lineas, portapapeles_log)
            continue

        _, buf = buffers.setdefault(ventana, (es_pt, []))
        if _aplicar_tecla_normal(buf, tecla):
            texto = "".join(buf).strip()
            buf.clear()
            if texto:
                lineas.append((ventana, es_pt, texto))

    for ventana, (es_pt, buf) in buffers.items():
        resto = "".join(buf).strip()
        if resto:
            lineas.append((ventana, es_pt, resto))

    return lineas, portapapeles_log


def agrupar_evidencia_por_dispositivo(
    eventos: list[dict[str, Any]],
    alertas_ventana: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Agrupa los comandos reconstruidos por dispositivo de red y asocia sus alias."""
    comandos_por_nodo: dict[str, list[str]] = {}
    alias_hostname: dict[str, str] = {}

    lineas, portapapeles_log = reconstruir_actividad(eventos)

    for ventana, es_pt, comando in lineas:
        nodo = identificar_nodo_pt(ventana, es_pt)
        if not nodo or nodo == "Topología":
            continue

        comandos_por_nodo.setdefault(nodo, []).append(comando)
        cmd_limpio = comando.removeprefix("[PEGADO] ").strip()
        nuevo_alias = extraer_nuevo_hostname(cmd_limpio)
        if nuevo_alias:
            alias_hostname[nodo] = nuevo_alias

    dispositivos_etiquetados = {
        f"{nodo} ({alias_hostname[nodo]})" if nodo in alias_hostname else nodo: cmds
        for nodo, cmds in comandos_por_nodo.items()
    }
    return {
        "alias_detectados": alias_hostname,
        "dispositivos": dispositivos_etiquetados,
        "eventos_portapapeles": portapapeles_log,
        "alertas_intencion_ventana": alertas_ventana or [],
    }
