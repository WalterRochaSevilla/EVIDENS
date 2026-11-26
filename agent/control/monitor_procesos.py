"""Escaneo en segundo plano de procesos de acceso remoto, túneles SSH/Telnet y VMs."""

import psutil

PROCESOS_REMOTO_Y_VM: dict[str, str] = {
    "anydesk.exe": "ACCESO_REMOTO_ANYDESK",
    "parsec.exe": "ACCESO_REMOTO_PARSEC",
    "parsecd.exe": "ACCESO_REMOTO_PARSEC",
    "teamviewer.exe": "ACCESO_REMOTO_TEAMVIEWER",
    "rustdesk.exe": "ACCESO_REMOTO_RUSTDESK",
    "mstsc.exe": "ACCESO_REMOTO_RDP",
    "ultraviewer_desktop.exe": "ACCESO_REMOTO_ULTRAVIEWER",
    "supremo.exe": "ACCESO_REMOTO_SUPREMO",
    "remoting_host.exe": "ACCESO_REMOTO_CHROME_RD",
    "nomachine.exe": "ACCESO_REMOTO_NOMACHINE",
    "putty.exe": "CONSOLA_REMOTA_PUTTY",
    "plink.exe": "CONSOLA_REMOTA_SSH",
    "ssh.exe": "CONSOLA_REMOTA_SSH",
    "telnet.exe": "CONSOLA_REMOTA_TELNET",
    "mobaxterm.exe": "CONSOLA_REMOTA_MOBAXTERM",
    "vmware.exe": "MAQUINA_VIRTUAL_VMWARE",
    "vmware-vmx.exe": "MAQUINA_VIRTUAL_VMWARE",
    "virtualboxvm.exe": "MAQUINA_VIRTUAL_VBOX",
    "vboxheadless.exe": "MAQUINA_VIRTUAL_VBOX",
}


class MonitorProcesosRemotos:
    """Detecta software de control remoto o VMs aunque estén minimizados en segundo plano."""

    def __init__(self) -> None:
        self._activos_notificados: set[str] = set()

    def reiniciar(self) -> None:
        """Limpia el registro de procesos notificados al iniciar una sesión."""
        self._activos_notificados.clear()

    def detectar_procesos_prohibidos(self) -> list[tuple[str, str]]:
        """Devuelve (etiqueta_alerta, nombre_proceso) sin duplicar instancias múltiples (ej. parsecd)."""
        encontrados_ahora: set[str] = set()
        nuevas_alertas: list[tuple[str, str]] = []

        try:
            for proc in psutil.process_iter(["name"]):
                nombre = (proc.info.get("name") or "").lower()
                if nombre in PROCESOS_REMOTO_Y_VM:
                    if nombre not in self._activos_notificados and nombre not in encontrados_ahora:
                        nuevas_alertas.append((PROCESOS_REMOTO_Y_VM[nombre], nombre))
                    encontrados_ahora.add(nombre)
        except Exception:
            pass

        self._activos_notificados = encontrados_ahora
        return nuevas_alertas
