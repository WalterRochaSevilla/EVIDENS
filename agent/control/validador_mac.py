import re
import socket

import psutil

_NO_HEXADECIMAL = re.compile(r"[^0-9A-Fa-f]")


def formatear_mac(mac: str) -> str:
    digitos = _NO_HEXADECIMAL.sub("", mac or "").upper()
    if len(digitos) != 12 or digitos == "000000000000":
        return ""
    return ":".join(digitos[i:i + 2] for i in range(0, 12, 2))


def es_mac_valida(mac: str) -> bool:
    return bool(formatear_mac(mac))


def _extraer_mac_de_interfaz(lista_direcciones: list) -> str:
    for dir_info in lista_direcciones:
        if dir_info.family.name == "AF_LINK":
            mac = formatear_mac(dir_info.address)
            if mac:
                return mac
    return ""


def obtener_todas_las_macs() -> list[dict[str, str]]:
    estadisticas = psutil.net_if_stats()
    resultado: list[dict[str, str]] = []
    for nombre, direcciones in psutil.net_if_addrs().items():
        stats = estadisticas.get(nombre)
        if not stats or not stats.isup:
            continue
        mac = _extraer_mac_de_interfaz(direcciones)
        if mac:
            resultado.append({"interfaz": nombre, "mac": mac})
    return resultado


def _obtener_ip_salida(ip_referencia: str = "8.8.8.8") -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.2)
            sock.connect((ip_referencia, 53))
            return str(sock.getsockname()[0])
    except OSError:
        return ""


def obtener_mac_principal() -> str:
    ip_activa = _obtener_ip_salida()
    for direcciones in psutil.net_if_addrs().values():
        ips_interfaz = {d.address for d in direcciones if d.family.name == "AF_INET"}
        if ip_activa and ip_activa in ips_interfaz:
            mac = _extraer_mac_de_interfaz(direcciones)
            if mac:
                return mac
    activas = obtener_todas_las_macs()
    return activas[0]["mac"] if activas else ""


def estacion_autorizada(macs_permitidas: list[str]) -> bool:
    permitidas = {formatear_mac(m) for m in macs_permitidas} - {""}
    locales = {item["mac"] for item in obtener_todas_las_macs()} - {""}
    return bool(locales & permitidas)