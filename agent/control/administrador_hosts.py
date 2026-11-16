import ctypes
import subprocess
import sys

from core.configuracion import (
    DOMINIOS_BLOQUEO_DEFECTO,
    HOSTS_FILE_PATH,
    HOSTS_TAG_END,
    HOSTS_TAG_START,
)


def es_administrador() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relanzar_como_administrador() -> bool:
    if es_administrador():
        return True
    parametros = " ".join(f'"{arg}"' for arg in sys.argv)
    respuesta = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, parametros, None, 1
    )
    return int(respuesta) > 32


def hosts_estan_bloqueados() -> bool:
    if not HOSTS_FILE_PATH.exists():
        return False
    try:
        contenido = HOSTS_FILE_PATH.read_text(encoding="utf-8", errors="surrogateescape")
        return HOSTS_TAG_START in contenido
    except OSError:
        return False


def _leer_lineas_hosts() -> list[str]:
    if not HOSTS_FILE_PATH.exists():
        return []
    return HOSTS_FILE_PATH.read_text(encoding="utf-8", errors="surrogateescape").splitlines()


def _escribir_lineas_hosts(lineas: list[str]) -> None:
    texto = "\r\n".join(lineas) + "\r\n"
    HOSTS_FILE_PATH.write_bytes(texto.encode("utf-8", errors="surrogateescape"))


def limpiar_bloqueos_evidens(lineas: list[str]) -> list[str]:
    conservadas: list[str] = []
    dentro_bloque = False
    for linea in lineas:
        if HOSTS_TAG_START in linea:
            dentro_bloque = True
        elif HOSTS_TAG_END in linea:
            dentro_bloque = False
        elif not dentro_bloque:
            conservadas.append(linea)
    return conservadas


def _construir_reglas_dominio(dominio: str) -> list[str]:
    limpio = dominio.strip().lower().removeprefix("www.")
    if not limpio:
        return []
    return [
        f"127.0.0.1 {limpio}",
        f"::1 {limpio}",
        f"127.0.0.1 www.{limpio}",
        f"::1 www.{limpio}",
    ]


def vaciar_cache_dns() -> None:
    subprocess.run(
        ["ipconfig", "/flushdns"],
        capture_output=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def aplicar_bloqueo(dominios: list[str] | None = None) -> bool:
    if not es_administrador():
        return False
    lista_dominios = dominios if dominios is not None else DOMINIOS_BLOQUEO_DEFECTO
    bloque: list[str] = [HOSTS_TAG_START]
    for dominio in sorted(set(lista_dominios)):
        bloque.extend(_construir_reglas_dominio(dominio))
    bloque.append(HOSTS_TAG_END)
    try:
        lineas_limpias = limpiar_bloqueos_evidens(_leer_lineas_hosts())
        _escribir_lineas_hosts(lineas_limpias + bloque)
        vaciar_cache_dns()
        return True
    except (PermissionError, OSError):
        return False


def restaurar_hosts() -> bool:
    if not es_administrador() or not HOSTS_FILE_PATH.exists():
        return False
    try:
        lineas_limpias = limpiar_bloqueos_evidens(_leer_lineas_hosts())
        _escribir_lineas_hosts(lineas_limpias)
        vaciar_cache_dns()
        return True
    except (PermissionError, OSError):
        return False