"""Persistencia incremental, plantilla .pkt por estudiante, reportes .txt y empaquetado ZIP."""

import hashlib, json, re, shutil, time, urllib.request, zipfile
from pathlib import Path
from typing import Any

from capture.buffer_video import consolidar_video_resumen
from capture.clasificador_cli import agrupar_evidencia_por_dispositivo
from core.configuracion import (
    DEFAULT_SERVER_URL,
    obtener_archivo_sesion_activa,
    obtener_directorio_base_evidencias,
    obtener_ruta_plantilla_pkt,
)
from core.exportador_txt import exportar_reportes_txt


def limpiar_nombre_carpeta(texto: str) -> str:
    """Convierte el nombre del estudiante en un identificador de archivo/carpeta seguro."""
    limpio = re.sub(r"[^A-Za-z0-9_\- ]", "", (texto or "").strip())
    return re.sub(r"\s+", "_", limpio) or "Estudiante"


def calcular_rutas_estudiante(nombre: str) -> tuple[Path, Path]:
    """Calcula la carpeta del estudiante (sin exponer el token en el nombre) y trabajo/."""
    base = obtener_directorio_base_evidencias()
    carpeta = base / limpiar_nombre_carpeta(nombre)
    return carpeta, carpeta / "trabajo"


def preparar_carpetas_estudiante(nombre: str) -> tuple[Path, Path, Path | None]:
    """Crea carpeta del estudiante, trabajo/ y copia plantilla_vacia.pkt con su nombre si existe."""
    carpeta, carpeta_trabajo = calcular_rutas_estudiante(nombre)
    (carpeta / "clips").mkdir(parents=True, exist_ok=True)
    carpeta_trabajo.mkdir(parents=True, exist_ok=True)

    ruta_pkt_asignado: Path | None = None
    plantilla = obtener_ruta_plantilla_pkt()
    if plantilla and plantilla.exists():
        destino_pkt = carpeta_trabajo / f"{limpiar_nombre_carpeta(nombre)}.pkt"
        if not destino_pkt.exists():
            try:
                shutil.copy2(plantilla, destino_pkt)
            except OSError:
                destino_pkt = None
        ruta_pkt_asignado = destino_pkt
    return carpeta, carpeta_trabajo, ruta_pkt_asignado


def anexar_eventos_jsonl(carpeta_estudiante: Path, nuevos_eventos: list[dict[str, Any]]) -> None:
    if not nuevos_eventos:
        return
    ruta_jsonl = carpeta_estudiante / "bitacora_comandos.jsonl"
    try:
        carpeta_estudiante.mkdir(parents=True, exist_ok=True)
        with ruta_jsonl.open("a", encoding="utf-8") as archivo:
            for ev in nuevos_eventos:
                archivo.write(json.dumps(ev, ensure_ascii=False) + "\n")
    except OSError:
        pass


def cargar_eventos_jsonl(carpeta_estudiante: Path) -> list[dict[str, Any]]:
    ruta_jsonl = carpeta_estudiante / "bitacora_comandos.jsonl"
    if not ruta_jsonl.exists():
        return []
    try:
        return [json.loads(l) for l in ruta_jsonl.read_text(encoding="utf-8").splitlines() if l.strip()]
    except Exception:
        return []


def guardar_checkpoint_estado(datos_estado: dict[str, Any]) -> None:
    try:
        obtener_archivo_sesion_activa().write_text(
            json.dumps(datos_estado, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        pass


def cargar_sesion_interrumpida() -> dict[str, Any] | None:
    archivo_sesion = obtener_archivo_sesion_activa()
    if not archivo_sesion.exists():
        return None
    try:
        datos = json.loads(archivo_sesion.read_text(encoding="utf-8"))
        return datos if datos.get("estado") == "EN_CURSO" else None
    except Exception:
        return None


def limpiar_marca_sesion_activa() -> None:
    try:
        archivo_sesion = obtener_archivo_sesion_activa()
        if archivo_sesion.exists():
            archivo_sesion.unlink()
    except OSError:
        pass


def listar_archivos_pkt(carpeta_estudiante: Path) -> list[str]:
    if not carpeta_estudiante.exists():
        return []
    return [str(p.relative_to(carpeta_estudiante)) for p in carpeta_estudiante.rglob("*.pkt") if p.is_file()]


def guardar_desarrollo_y_empaquetar_zip(carpeta_estudiante: Path, evidencia: dict[str, Any]) -> tuple[Path, str]:
    """Escribe desarrollo_examen.json, los 2 reportes .txt, limpia el .jsonl y empaqueta .zip."""
    carpeta_estudiante.mkdir(parents=True, exist_ok=True)
    (carpeta_estudiante / "desarrollo_examen.json").write_text(
        json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    exportar_reportes_txt(carpeta_estudiante, evidencia)

    ruta_jsonl = carpeta_estudiante / "bitacora_comandos.jsonl"
    if ruta_jsonl.exists():
        try:
            ruta_jsonl.unlink()
        except OSError:
            pass

    nombre_zip = f"entrega_{carpeta_estudiante.name}.zip"
    ruta_zip = carpeta_estudiante / nombre_zip
    archivos = [
        p for p in carpeta_estudiante.rglob("*")
        if p.is_file() and p.name != nombre_zip and not p.name.endswith(".sha256")
    ]
    with zipfile.ZipFile(ruta_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for archivo in archivos:
            zf.write(archivo, arcname=archivo.relative_to(carpeta_estudiante))

    sha256 = hashlib.sha256(ruta_zip.read_bytes()).hexdigest()
    (carpeta_estudiante / "integridad.sha256").write_text(
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
    historial_ventanas: list[dict[str, Any]],
    clips: list[dict[str, Any]],
    cierres_forzados: list[str],
    archivos_pkt: list[str],
) -> str:
    """Consolida eventos, genera JSON + 2 TXT + MP4 único, comprime el .zip y resume."""
    eventos_totales = cargar_eventos_jsonl(carpeta_estudiante)
    evidencia = agrupar_evidencia_por_dispositivo(eventos_totales, alertas_ventana, historial_ventanas)
    video_resumen = consolidar_video_resumen(carpeta_estudiante, clips)
    evidencia["video_consolidado"] = video_resumen
    evidencia["clips_video"] = clips
    evidencia["archivos_pkt"] = archivos_pkt
    evidencia["incidentes_recuperacion"] = cierres_forzados
    evidencia["metadata"] = {
        "estudiante": nombre, "token": token, "station_mac": mac,
        "estado_sesion": motivo_cierre, "fecha_entrega": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    ruta_zip, sha256 = guardar_desarrollo_y_empaquetar_zip(carpeta_estudiante, evidencia)
    total_cmds = sum(len(v) for v in evidencia["dispositivos"].values())
    linea_video = f"• Video consolidado: {video_resumen['archivo']} ({video_resumen['duracion_total_seg']} s)\n" if video_resumen else ""
    return (
        f"Sesión concluida ({motivo_cierre}). Cortafuegos restaurado.\n\n"
        f"• Estudiante: {nombre}\n"
        f"• Dispositivos PT: {len(evidencia['dispositivos'])} | Comandos CLI: {total_cmds}\n"
        f"• Archivos .pkt: {len(archivos_pkt)} | Alertas: {len(alertas_ventana)} | Clips: {len(clips)}\n"
        f"{linea_video}"
        f"• Reportes: desarrollo_examen.json, cronologia_completa.txt y comandos_por_dispositivo.txt\n"
        f"• Paquete ZIP: {ruta_zip.name}\n• SHA-256: {sha256[:32]}..."
    )


def consultar_orden_servidor(token: str, mac: str) -> dict[str, Any] | None:
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
