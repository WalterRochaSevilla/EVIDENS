"""Clasificador CLI v2 para Cisco Packet Tracer: cronología general, nodos y origen de pegado."""

import re
import time
from typing import Any

from capture.normalizador_ios import EditorLineaCLI, normalizar_comando_ios
from capture.recolector_teclado import es_origen_copia_permitido

PATRON_VENTANA_DISPOSITIVO = re.compile(
    r"^\s*((?:Multilayer Switch|Router|Switch|Server|Laptop|PC)\s*\d*(?:\(\d+\))?)"
    r"(?:\s*-\s*.*)?$",
    re.IGNORECASE,
)
PATRON_COMANDO_HOSTNAME = re.compile(
    r"^\s*hos(?:t(?:name)?)?\s+([A-Za-z0-9_\-\.]+)\s*$", re.IGNORECASE
)
_VENTANAS_DIALOGO_IGNORAR = (
    "save file", "open file", "guardar", "abrir", "print", "preferences", "options",
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
    return coincidencia.group(1).strip() if coincidencia else limpio


def extraer_nuevo_hostname(comando: str) -> str | None:
    """Detecta si el comando asigna un nuevo hostname en IOS (hos, host o hostname)."""
    coincidencia = PATRON_COMANDO_HOSTNAME.match(comando.strip())
    return coincidencia.group(1) if coincidencia else None


def _procesar_portapapeles(
    ev: dict[str, Any],
    entradas: list[dict[str, Any]],
    portapapeles_log: list[dict[str, Any]],
) -> None:
    tecla = str(ev.get("tecla", ""))
    texto_clip = str(ev.get("portapapeles", "")).strip()
    ventana = str(ev.get("ventana", "")) or "SIN_VENTANA"
    es_pt = bool(ev.get("es_packet_tracer", False))
    ts = float(ev.get("timestamp", 0.0))
    origen = ev.get("origen_copia") or {}
    proc_origen = str(origen.get("proceso", ""))

    if tecla == "[CTRL+V]" and texto_clip:
        clasif = "REUTILIZACION_PERMITIDA" if es_origen_copia_permitido(proc_origen) else "ORIGEN_EXTERNO_SOSPECHOSO"
    else:
        clasif = "REUTILIZACION_PERMITIDA"

    portapapeles_log.append({
        "hora": time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "",
        "accion": tecla,
        "ventana_destino": ventana,
        "origen_proceso": proc_origen or "packettracer",
        "origen_ventana": str(origen.get("ventana", "")),
        "clasificacion": clasif,
        "contenido": texto_clip[:300] if texto_clip else "[Objeto de topología en Packet Tracer]",
    })
    if tecla == "[CTRL+V]" and texto_clip:
        etiqueta = f"pegado_{proc_origen or 'local'}"
        for linea in texto_clip.splitlines():
            if linea.strip():
                entradas.append({"ts": ts, "ventana": ventana, "es_pt": es_pt, "origen": etiqueta, "texto": linea.strip()})


def agrupar_evidencia_por_dispositivo(
    eventos: list[dict[str, Any]],
    alertas_ventana: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Reconstruye la cronología general y agrupa los comandos por dispositivo con alias."""
    editores: dict[str, tuple[bool, EditorLineaCLI]] = {}
    entradas: list[dict[str, Any]] = []
    portapapeles_log: list[dict[str, Any]] = []

    for ev in sorted(eventos, key=lambda x: x.get("timestamp", 0.0)):
        ventana = str(ev.get("ventana", "")).strip() or "SIN_VENTANA"
        es_pt = bool(ev.get("es_packet_tracer", False))
        tecla = str(ev.get("tecla", ""))
        ts = float(ev.get("timestamp", 0.0))

        if tecla in ("[CTRL+C]", "[CTRL+V]"):
            _procesar_portapapeles(ev, entradas, portapapeles_log)
            continue

        _, editor = editores.setdefault(ventana, (es_pt, EditorLineaCLI()))
        resultado = editor.procesar_tecla(tecla)
        if resultado:
            entradas.append({"ts": ts, "ventana": ventana, "es_pt": es_pt, "origen": resultado[0], "texto": resultado[1]})

    for ventana, (es_pt, editor) in editores.items():
        resto = "".join(editor.chars).strip()
        if resto:
            entradas.append({"ts": 0.0, "ventana": ventana, "es_pt": es_pt, "origen": "teclado", "texto": resto})

    alias_hostname: dict[str, str] = {}
    comandos_por_nodo: dict[str, list[str]] = {}
    cronologia_raw: list[dict[str, Any]] = []

    for item in entradas:
        nodo = identificar_nodo_pt(item["ventana"], item["es_pt"])
        if not nodo or nodo == "Topología":
            continue
        cmd_raw = item["texto"]
        cmd_norm = normalizar_comando_ios(cmd_raw)
        nuevo_alias = extraer_nuevo_hostname(cmd_raw)
        if nuevo_alias:
            alias_hostname[nodo] = nuevo_alias
        comandos_por_nodo.setdefault(nodo, []).append(cmd_norm)
        cronologia_raw.append({
            "hora": time.strftime("%H:%M:%S", time.localtime(item["ts"])) if item["ts"] else "",
            "nodo_base": nodo,
            "comando": cmd_raw,
            "normalizado": cmd_norm,
            "origen": item["origen"],
        })

    cronologia = [
        {
            "hora": c["hora"],
            "dispositivo": f"{c['nodo_base']} ({alias_hostname[c['nodo_base']]})" if c["nodo_base"] in alias_hostname else c["nodo_base"],
            "comando": c["comando"],
            "normalizado": c["normalizado"],
            "origen": c["origen"],
        }
        for c in cronologia_raw
    ]
    dispositivos = {
        f"{nodo} ({alias_hostname[nodo]})" if nodo in alias_hostname else nodo: cmds
        for nodo, cmds in comandos_por_nodo.items()
    }
    return {
        "alias_detectados": alias_hostname,
        "cronologia_general": cronologia,
        "dispositivos": dispositivos,
        "eventos_portapapeles": portapapeles_log,
        "alertas_intencion_ventana": alertas_ventana or [],
    }
