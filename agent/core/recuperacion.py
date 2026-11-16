"""Persistencia incremental (.jsonl), checkpoints ligeros, recuperación y empaquetado ZIP."""

import hashlib
import json
import re
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from capture.clasificador_cli import agrupar_evidencia_por_dispositivo
from core.configuracion import (
    DEFAULT_SERVER_URL,
    obtener_archivo_sesion_activa,
    obtener_directorio_base_evidencias,
)


def limpiar_nombre_carpeta(texto: str) -> str:
    """Convierte el nombre del estudiante en un nombre de directorio seguro en Windows."""
    limpio = re.sub(r"[^A-Za-z0-9_\- ]", "", (texto or "").strip())
    return re.sub(r"\s+", "_", limpio) or "Estudiante"


def preparar_carpetas_estudiante(nombre: str, token: str) -> tuple[Path, Path]:
    """Crea la carpeta del estudiante y la subcarpeta trabajo/ para el archivo .pkt."""
    base = obtener_directorio_base_evidencias()
    carpeta = base / f"{limpiar_nombre_carpeta(nombre)}_{token.strip()}"
    carpeta_trabajo = carpeta / "trabajo"
    (carpeta / "clips").mkdir(parents=True, exist_ok=True)
    carpeta_trabajo.mkdir(parents=True, exist_ok=True)
    return carpeta, carpeta_trabajo


def anexar_eventos_jsonl(carpeta_estudiante: Path, nuevos_eventos: list[dict[str, Any]]) -> None:
    """Anexa únicamente los eventos nuevos al archivo eventos_teclado.jsonl en O(k)."""
    if not nuevos_eventos:
        return
    ruta_jsonl = carpeta_estudiante / "eventos_teclado.jsonl"
    try:
        carpeta_estudiante.mkdir(parents=True, exist_ok=True)
        with ruta_jsonl.open("a", encoding="utf-8") as archivo:
            for ev in nuevos_eventos:
                archivo.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        pass


def cargar_eventos_jsonl(carpeta_estudiante: Path) -> list[dict[str, Any]]:
    """Lee todos los eventos almacenados en eventos_teclado.jsonl al cerrar o recuperar."""
    ruta_jsonl = carpeta_estudiante / "eventos_teclado.jsonl"
    if not ruta_jsonl.exists():
        return []
    try:
        return [
            json.loads(linea)
            for linea in ruta_jsonl.read_text(encoding="utf-8").splitlines()
            if linea.strip()
        ]
    except Exception:
        return []


def guardar_checkpoint_estado(datos_estado: dict[str, Any]) -> None:
    """Guarda únicamente el estado ligero de la sesión activa (sin reescribir el historial)."""
    try:
        obtener_archivo_sesion_activa().write_text(
            json.dumps(datos_estado, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def cargar_sesion_interrumpida() -> dict[str, Any] | None:
    """Devuelve los datos de la sesión si el proceso se cerró abruptamente estando EN_CURSO."""
    archivo_sesion = obtener_archivo_sesion_activa()
    if not archivo_sesion.exists():
        return None
    try:
        datos = json.loads(archivo_sesion.read_text(encoding="utf-8"))
        return datos if datos.get("estado") == "EN_CURSO" else None
    except Exception:
        return None


def limpiar_marca_sesion_activa() -> None:
    """Elimina la marca de sesión activa cuando el examen se entrega formalmente."""
    try:
        archivo_sesion = obtener_archivo_sesion_activa()
        if archivo_sesion.exists():
            archivo_sesion.unlink()
    except OSError:
        pass


def listar_archivos_pkt(carpeta_estudiante: Path) -> list[str]:
    """Busca archivos .pkt dentro de la carpeta del estudiante (incluida trabajo/)."""
    if not carpeta_estudiante.exists():
        return []
    return [
        str(p.relative_to(carpeta_estudiante))
        for p in carpeta_estudiante.rglob("*.pkt")
        if p.is_file()
    ]


def guardar_keylog_y_empaquetar_zip(
    carpeta_estudiante: Path, token: str, evidencia: dict[str, Any]
) -> tuple[Path, str]:
    """Escribe el JSON consolidado, comprime toda la carpeta en .zip y genera su SHA-256."""
    carpeta_estudiante.mkdir(parents=True, exist_ok=True)
    ruta_json = carpeta_estudiante / f"keylog_{token}.json"
    ruta_json.write_text(json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8")

    ruta_zip = carpeta_estudiante.parent / f"{carpeta_estudiante.name}.zip"
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for archivo in carpeta_estudiante.rglob("*"):
            if archivo.is_file():
                zf.write(archivo, arcname=archivo.relative_to(carpeta_estudiante))

    sha256 = hashlib.sha256(ruta_zip.read_bytes()).hexdigest()
    (carpeta_estudiante / f"integridad_{token}.sha256").write_text(
        f"{sha256}  {ruta_zip.name}\nGenerado: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
        encoding="utf-8",
    )
    return ruta_zip, sha256


def consolidar_y_empaquetar_entrega(
    carpeta_estudiante: Path,
    nombre: str,
    token: str,
    mac: str,
    motivo_cierre: str,
    alertas_ventana: list[dict[str, Any]],
    clips: list[dict[str, Any]],
    cierres_forzados: list[str],
    archivos_pkt: list[str],
) -> str:
    """Consolida eventos .jsonl, genera el keylog.json, comprime el .zip y devuelve el resumen."""
    eventos_totales = cargar_eventos_jsonl(carpeta_estudiante)
    evidencia = agrupar_evidencia_por_dispositivo(eventos_totales, alertas_ventana)
    evidencia["clips_video"] = clips
    evidencia["archivos_pkt"] = archivos_pkt
    evidencia["incidentes_recuperacion"] = cierres_forzados
    evidencia["metadata"] = {
        "estudiante": nombre,
        "token": token,
        "station_mac": mac,
        "estado_sesion": motivo_cierre,
        "fecha_entrega": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ruta_zip, sha256 = guardar_keylog_y_empaquetar_zip(carpeta_estudiante, token, evidencia)
    total_cmds = sum(len(v) for v in evidencia["dispositivos"].values())
    return (
        f"Sesión concluida ({motivo_cierre}). Cortafuegos restaurado.\n\n"
        f"• Estudiante: {nombre} (Token: {token})\n"
        f"• Dispositivos PT: {len(evidencia['dispositivos'])} | Comandos CLI: {total_cmds}\n"
        f"• Archivos .pkt: {len(archivos_pkt)} | Alertas: {len(alertas_ventana)} | Clips: {len(clips)}\n"
        f"• Paquete ZIP: {ruta_zip}\n"
        f"• SHA-256: {sha256[:32]}..."
    )


def consultar_orden_servidor(token: str, mac: str) -> dict[str, Any] | None:
    """Consulta sin conexión persistente si el docente envió ajuste de tiempo, habilitación o corte."""
    if not token:
        return None
    url = f"{DEFAULT_SERVER_URL.rstrip('/')}/api/v1/examen/control/{token}?mac={mac}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=0.35) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None
