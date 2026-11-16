"""Obtención y validación de la dirección física (MAC) usando la ruta hacia el servidor LAN."""

import re
import socket
from urllib.parse import urlparse

import psutil

from core.configuracion import DEFAULT_SERVER_URL

_NO_HEXADECIMAL = re.compile(r"[^0-9A-Fa-f]")
_ADAPTADORES_VIRTUALES = (
    "radmin",
    "tailscale",
    "virtualbox",
    "vmware",
    "loopback",
    "teredo",
    "bluetooth",
    "pseudo",
)


def formatear_mac(mac: str) -> str:
    """Normaliza una dirección MAC al formato XX:XX:XX:XX:XX:XX."""
    digitos = _NO_HEXADECIMAL.sub("", mac or "").upper()
    if len(digitos) != 12 or digitos == "000000000000":
        return ""
    return ":".join(digitos[i : i + 2] for i in range(0, 12, 2))


def es_mac_valida(mac: str) -> bool:
    """Comprueba si la dirección MAC es válida."""
    return bool(formatear_mac(mac))


def _extraer_mac_de_interfaz(lista_direcciones: list) -> str:
    for dir_info in lista_direcciones:
        if dir_info.family.name == "AF_LINK":
            mac = formatear_mac(dir_info.address)
            if mac:
                return mac
    return ""


def obtener_todas_las_macs() -> list[dict[str, str]]:
    """Lista las interfaces activas (isup) priorizando adaptadores físicos frente a virtuales."""
    estadisticas = psutil.net_if_stats()
    fisicas: list[dict[str, str]] = []
    virtuales: list[dict[str, str]] = []

    for nombre, direcciones in psutil.net_if_addrs().items():
        stats = estadisticas.get(nombre)
        if not stats or not stats.isup:
            continue
        mac = _extraer_mac_de_interfaz(direcciones)
        if not mac:
            continue
        item = {"interfaz": nombre, "mac": mac}
        if any(v in nombre.lower() for v in _ADAPTADORES_VIRTUALES):
            virtuales.append(item)
        else:
            fisicas.append(item)
    return fisicas + virtuales


def _obtener_ip_referencia_servidor() -> str:
    """Obtiene el host/IP del servidor configurado sin depender de salida a Internet."""
    host = (urlparse(DEFAULT_SERVER_URL).hostname or "").strip()
    if host and host not in ("localhost", "127.0.0.1", "::1"):
        return host
    return "10.255.255.255"


def _obtener_ip_salida(ip_referencia: str | None = None) -> str:
    """Determina la IP local de salida hacia el servidor mediante tabla de enrutamiento UDP."""
    destino = ip_referencia or _obtener_ip_referencia_servidor()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect((destino, 8000))
            ip_local = str(sock.getsockname()[0])
            return "" if ip_local.startswith("127.") else ip_local
    except OSError:
        return ""


def obtener_mac_principal() -> str:
    """Retorna la dirección MAC de la interfaz física empleada hacia la red del servidor."""
    ip_activa = _obtener_ip_salida()
    for nombre, direcciones in psutil.net_if_addrs().items():
        if any(v in nombre.lower() for v in _ADAPTADORES_VIRTUALES):
            continue
        ips_interfaz = {d.address for d in direcciones if d.family.name == "AF_INET"}
        if ip_activa and ip_activa in ips_interfaz:
            mac = _extraer_mac_de_interfaz(direcciones)
            if mac:
                return mac
    activas = obtener_todas_las_macs()
    return activas[0]["mac"] if activas else ""


def estacion_autorizada(macs_permitidas: list[str]) -> bool:
    """Verifica si alguna MAC activa del equipo figura en la lista autorizada."""
    permitidas = {formatear_mac(m) for m in macs_permitidas} - {""}
    locales = {item["mac"] for item in obtener_todas_las_macs()} - {""}
    return bool(locales & permitidas)
