"""Búfer circular en RAM, generación de clips .mp4 (H.264) y video consolidado de alertas."""

import re, subprocess, time
from collections import deque
from io import BytesIO
from pathlib import Path
from typing import Any

import mss, mss.tools

try:
    from PIL import Image, ImageDraw
    PILLOW_DISPONIBLE = True
except ImportError:
    Image, ImageDraw = None, None
    PILLOW_DISPONIBLE = False

try:
    import imageio_ffmpeg
    FFMPEG_EXE: str | None = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = None

ANCHO_VIDEO, ALTO_VIDEO, FPS_VIDEO = 960, 540, 2
_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _normalizar_cuadro_rgb(datos_jpeg: bytes) -> bytes:
    """Ajusta el cuadro al lienzo estándar 960x540 (dimensiones pares exigidas por H.264)."""
    img = Image.open(BytesIO(datos_jpeg)).convert("RGB")
    if img.size != (ANCHO_VIDEO, ALTO_VIDEO):
        lienzo = Image.new("RGB", (ANCHO_VIDEO, ALTO_VIDEO), (15, 23, 42))
        img.thumbnail((ANCHO_VIDEO, ALTO_VIDEO))
        lienzo.paste(img, ((ANCHO_VIDEO - img.width) // 2, (ALTO_VIDEO - img.height) // 2))
        return lienzo.tobytes()
    return img.tobytes()


def _crear_portada_incidente(motivo: str, hora: str) -> bytes:
    """Genera una tarjeta separadora (960x540) con la hora y el motivo de la alerta."""
    lienzo = Image.new("RGB", (ANCHO_VIDEO, ALTO_VIDEO), (15, 23, 42))
    draw = ImageDraw.Draw(lienzo)
    draw.rectangle([40, 190, ANCHO_VIDEO - 40, 350], fill=(26, 54, 93), outline=(56, 189, 248), width=3)
    draw.text((70, 225), f"EVIDENS - INCIDENTE REGISTRADO [{hora}]", fill=(125, 211, 252))
    draw.text((70, 275), f"MOTIVO: {motivo}", fill=(255, 255, 255))
    return lienzo.tobytes()


def _codificar_mp4_h264(ruta_salida: Path, cuadros_rgb: list[bytes]) -> bool:
    """Codifica cuadros RGB crudos en un .mp4 H.264 compatible con navegador web y Windows."""
    if not FFMPEG_EXE or not cuadros_rgb:
        return False
    cmd = [
        FFMPEG_EXE, "-y", "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "rgb24", "-s", f"{ANCHO_VIDEO}x{ALTO_VIDEO}", "-r", str(FPS_VIDEO),
        "-i", "-", "-an", "-vcodec", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(ruta_salida),
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW)
        assert proc.stdin is not None
        for cuadro in cuadros_rgb:
            proc.stdin.write(cuadro)
        proc.stdin.close()
        return proc.wait(timeout=25) == 0 and ruta_salida.exists()
    except Exception:
        return False


def consolidar_video_resumen(
    carpeta_estudiante: Path, clips_generados: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Une todos los clips .mp4 en un solo resumen_incidentes.mp4 con marcas de tiempo."""
    if not FFMPEG_EXE or not clips_generados:
        return None
    carpeta_clips = carpeta_estudiante / "clips"
    rutas_validas = [
        (carpeta_clips / str(info["archivo"]), info)
        for info in clips_generados
        if str(info.get("archivo", "")).endswith(".mp4")
        and (carpeta_clips / str(info["archivo"])).exists()
        and (carpeta_clips / str(info["archivo"])).stat().st_size > 0
    ]
    if not rutas_validas:
        return None

    lista_concat = carpeta_clips / "_concat_lista.txt"
    ruta_resumen = carpeta_estudiante / "resumen_incidentes.mp4"
    capitulos: list[dict[str, Any]] = []
    offset_seg = 0.0

    try:
        lista_concat.write_text("\n".join(f"file '{r.resolve().as_posix()}'" for r, _ in rutas_validas), encoding="utf-8")
        cmd = [FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", str(lista_concat), "-c", "copy", "-movflags", "+faststart", str(ruta_resumen)]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=_NO_WINDOW, timeout=30)
        if res.returncode != 0 or not ruta_resumen.exists():
            return None

        for _, info in rutas_validas:
            dur = float(info.get("duracion_seg", round(info.get("cuadros", 1) / FPS_VIDEO, 1)))
            mins, segs = divmod(int(offset_seg), 60)
            capitulos.append({
                "marca_tiempo": f"{mins:02d}:{segs:02d}", "inicio_seg": round(offset_seg, 1),
                "duracion_seg": dur, "hora_real": info.get("hora", ""),
                "motivo": info.get("motivo", ""), "clip_origen": info.get("archivo", ""),
            })
            offset_seg += dur
        return {"archivo": ruta_resumen.name, "duracion_total_seg": round(offset_seg, 1), "total_clips": len(capitulos), "capitulos": capitulos}
    except Exception:
        return None
    finally:
        try:
            if lista_concat.exists():
                lista_concat.unlink()
        except OSError:
            pass


class BufferCircularVideo:
    """Mantiene los últimos N cuadros comprimidos en RAM y vuelca clips .mp4 (H.264) en disco."""

    def __init__(self, max_cuadros: int = 20) -> None:
        self._buffer_ram: deque[bytes] = deque(maxlen=max_cuadros)
        self.clips_generados: list[dict[str, Any]] = []
        self._ultimo_volcado_por_motivo: dict[str, float] = {}

    def capturar_cuadro(self) -> None:
        try:
            with getattr(mss, "MSS", mss.mss)() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                if PILLOW_DISPONIBLE and Image is not None:
                    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                    img.thumbnail((ANCHO_VIDEO, ALTO_VIDEO))
                    flujo = BytesIO()
                    img.save(flujo, format="JPEG", quality=55)
                    self._buffer_ram.append(flujo.getvalue())
                else:
                    self._buffer_ram.append(mss.tools.to_png(raw.rgb, raw.size, level=6))
        except Exception:
            pass

    def volcar_clip(self, carpeta_clips: Path, motivo: str) -> str | None:
        """Guarda en disco un clip .mp4 (H.264) con portada de alerta y los cuadros del búfer."""
        ahora = time.time()
        if (ahora - self._ultimo_volcado_por_motivo.get(motivo, 0.0)) < 4.0:
            return None
        if not self._buffer_ram:
            self.capturar_cuadro()
        if not self._buffer_ram:
            return None

        self._ultimo_volcado_por_motivo[motivo] = ahora
        try:
            carpeta_clips.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None

        hora_txt, sello = time.strftime("%H:%M:%S"), time.strftime("%H%M%S")
        motivo_limpio = re.sub(r"[^A-Za-z0-9_]", "_", motivo).strip("_") or "ALERTA"
        instantanea = list(self._buffer_ram)

        try:
            if PILLOW_DISPONIBLE and Image is not None and FFMPEG_EXE:
                ruta_clip = carpeta_clips / f"clip_{motivo_limpio}_{sello}.mp4"
                portada = _crear_portada_incidente(motivo, hora_txt)
                cuadros_rgb = [portada, portada] + [_normalizar_cuadro_rgb(b) for b in instantanea]
                if _codificar_mp4_h264(ruta_clip, cuadros_rgb):
                    total = len(cuadros_rgb)
                    self.clips_generados.append({
                        "timestamp": round(ahora, 2), "hora": hora_txt, "motivo": motivo,
                        "archivo": ruta_clip.name, "cuadros": total, "duracion_seg": round(total / FPS_VIDEO, 1),
                    })
                    return ruta_clip.name

            if PILLOW_DISPONIBLE and Image is not None:
                ruta_gif = carpeta_clips / f"clip_{motivo_limpio}_{sello}.gif"
                cuadros = [Image.open(BytesIO(b)) for b in instantanea]
                cuadros[0].save(ruta_gif, save_all=True, append_images=cuadros[1:], duration=350, loop=0)
                self.clips_generados.append({
                    "timestamp": round(ahora, 2), "hora": hora_txt, "motivo": motivo,
                    "archivo": ruta_gif.name, "cuadros": len(cuadros), "duracion_seg": round(len(cuadros) * 0.35, 1),
                })
                return ruta_gif.name
        except Exception:
            pass
        return None
