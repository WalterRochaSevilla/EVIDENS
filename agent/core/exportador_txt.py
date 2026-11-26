"""Generación de reportes legibles (.txt): cronología completa y comandos por dispositivo."""

from pathlib import Path
from typing import Any


def exportar_reportes_txt(carpeta_estudiante: Path, evidencia: dict[str, Any]) -> tuple[Path, Path]:
    """Genera cronologia_completa.txt (ventanas, alertas y CLI) y comandos_por_dispositivo.txt."""
    meta = evidencia.get("metadata", {})
    encabezado = [
        "================================================================",
        f"EVIDENS - ESTUDIANTE : {meta.get('estudiante', '')}",
        f"ESTACIÓN (MAC)       : {meta.get('station_mac', '')}",
        f"ESTADO DE CIERRE     : {meta.get('estado_sesion', '')}",
        f"FECHA DE ENTREGA     : {meta.get('fecha_entrega', '')}",
        "================================================================",
        "",
    ]

    # 1) cronologia_completa.txt: toda la línea de tiempo (ventanas + alertas + comandos)
    lineas_crono = list(encabezado) + ["--- CRONOLOGÍA GENERAL DE ACTIVIDAD (VENTANAS, ALERTAS Y CLI) ---", ""]
    for item in evidencia.get("cronologia_general", []):
        hora = item.get("hora", "--:--:--")
        tipo = str(item.get("tipo", "evento")).upper()
        if tipo == "VENTANA":
            dur = item.get("duracion_seg", 0)
            lineas_crono.append(f"[{hora}] [VENTANA] ({dur}s) {item.get('proceso', '')} -> {item.get('ventana', '')}")
        elif tipo == "ALERTA":
            clip = item.get("clip_evidencia", "sin_clip")
            lineas_crono.append(
                f"[{hora}] [⚠ ALERTA] {item.get('motivo', '')} | {item.get('proceso', '')} | "
                f"{item.get('ventana', '')} (clip: {clip})"
            )
        else:
            disp = item.get("dispositivo", "")
            norm = item.get("normalizado", item.get("comando", ""))
            orig = item.get("origen", "")
            lineas_crono.append(f"[{hora}] [CLI] [{disp}] {norm}  ({orig})")

    ruta_crono = carpeta_estudiante / "cronologia_completa.txt"
    ruta_crono.write_text("\n".join(lineas_crono) + "\n", encoding="utf-8")

    # 2) comandos_por_dispositivo.txt: vista limpia agrupada por equipo de red
    lineas_disp = list(encabezado) + ["--- COMANDOS DE CONFIGURACIÓN POR DISPOSITIVO ---", ""]
    dispositivos = evidencia.get("dispositivos", {})
    if not dispositivos:
        lineas_disp.append("(No se registraron comandos CLI en Cisco Packet Tracer)")
    else:
        for nombre_disp, comandos in dispositivos.items():
            lineas_disp.append(f"=== {nombre_disp} ===")
            for cmd in comandos:
                lineas_disp.append(f"  {cmd}")
            lineas_disp.append("")

    archivos_pkt = evidencia.get("archivos_pkt", [])
    lineas_disp.append("--- ARCHIVOS .PKT RECOLECTADOS ---")
    lineas_disp.extend(f"  • {p}" for p in archivos_pkt) if archivos_pkt else lineas_disp.append("  (Ninguno)")

    ruta_disp = carpeta_estudiante / "comandos_por_dispositivo.txt"
    ruta_disp.write_text("\n".join(lineas_disp) + "\n", encoding="utf-8")
    return ruta_crono, ruta_disp
