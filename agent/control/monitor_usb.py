"""Monitoreo de unidades de almacenamiento extraíbles (USB) durante el examen."""

import psutil


def unidades_extraibles() -> set[str]:
    """Devuelve el conjunto de letras de unidades extraíbles o CD-ROM montadas."""
    try:
        return {
            p.device
            for p in psutil.disk_partitions(all=False)
            if "removable" in p.opts.lower() or "cdrom" in p.opts.lower()
        }
    except Exception:
        return set()


class MonitorUSB:
    """Detecta la inserción de nuevas memorias USB respecto al estado inicial."""

    def __init__(self) -> None:
        self._unidades_conocidas: set[str] = unidades_extraibles()

    def reiniciar_base(self) -> None:
        """Toma una instantánea de las unidades presentes al iniciar el examen."""
        self._unidades_conocidas = unidades_extraibles()

    def detectar_nuevas_unidades(self) -> list[str]:
        """Retorna las unidades extraíbles recién conectadas y actualiza el estado."""
        actuales = unidades_extraibles()
        nuevas = sorted(actuales - self._unidades_conocidas)
        self._unidades_conocidas = actuales
        return nuevas
