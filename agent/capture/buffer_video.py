import re
import time
from collections import deque
from io import BytesIO
from pathlib import Path
from typing import Any

import mss
import mss.tools

try:
    from PIL import Image
    PILLOW_DISPONIBLE = True
except ImportError:
    Image = None
    PILLOW_DISPONIBLE = False


def _crear_instancia_mss() -> Any:
    """Usa mss.MSS() en versiones modernas evitando el DeprecationWarning de mss.mss()."""
    clase_mss = getattr(mss, "MSS", mss.mss)
    return clase_mss()


class BufferCircularVideo:
    """Mantiene los últimos N cuadros comprimidos en RAM y vuelca clips en disco."""

    def __init__(self, max_cuadros: int = 20) -> None:
        self._buffer_ram: deque[bytes] = deque(maxlen=max_cuadros)
        self.clips_generados: list[dict[str, Any]] = []
        self._ultimo_volcado_por_motivo: dict[str, float] = {}

    def capturar_cuadro(self) -> None:
        """Captura un cuadro de la pantalla principal y lo almacena comprimido en RAM."""
        try:
            with _crear_instancia_mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                raw = sct.grab(monitor)
                if PILLOW_DISPONIBLE and Image is not None:
                    img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                    img.thumbnail((960, 540))
                    flujo = BytesIO()
                    img.save(flujo, format="JPEG", quality=50)
                    self._buffer_ram.append(flujo.getvalue())
                else:
                    png_bytes = mss.tools.to_png(raw.rgb, raw.size, level=6)
                    self._buffer_ram.append(png_bytes)
        except Exception:
            pass

    def volcar_clip(self, carpeta_clips: Path, motivo: str) -> str | None:
        """Guarda en disco el clip de los últimos cuadros en RAM cuando ocurre una alerta."""
        ahora = time.time()
        ultimo_ts = self._ultimo_volcado_por_motivo.get(motivo, 0.0)
        if (ahora - ultimo_ts) < 4.0:
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

        sello = time.strftime("%H%M%S")
        motivo_limpio = re.sub(r"[^A-Za-z0-9_]", "_", motivo).strip("_") or "ALERTA"

        try:
            if PILLOW_DISPONIBLE and Image is not None:
                ruta_clip = carpeta_clips / f"clip_{motivo_limpio}_{sello}.gif"
                cuadros = [Image.open(BytesIO(b)) for b in list(self._buffer_ram)]
                if not cuadros:
                    return None
                cuadros[0].save(
                    ruta_clip,
                    save_all=True,
                    append_images=cuadros[1:],
                    duration=350,
                    loop=0,
                )
                num_cuadros = len(cuadros)
            else:
                ruta_clip = carpeta_clips / f"clip_{motivo_limpio}_{sello}.png"
                ruta_clip.write_bytes(self._buffer_ram[-1])
                num_cuadros = 1

            info = {
                "timestamp": round(ahora, 2),
                "hora": time.strftime("%H:%M:%S"),
                "motivo": motivo,
                "archivo": ruta_clip.name,
                "cuadros": num_cuadros,
            }
            self.clips_generados.append(info)
            return ruta_clip.name
        except Exception:
            return None
