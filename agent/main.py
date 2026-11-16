import json
import sys
import time
from pathlib import Path
from tkinter import messagebox

directorio_actual = Path(__file__).resolve().parent
if str(directorio_actual) not in sys.path:
    sys.path.insert(0, str(directorio_actual))

from core.configuracion import EVIDENS_TEMP_DIR, inicializar_directorios_locales
from control.validador_mac import obtener_mac_principal
from control.administrador_hosts import (
    aplicar_bloqueo,
    es_administrador,
    hosts_estan_bloqueados,
    restaurar_hosts,
)
from capture.recolector_teclado import RecolectorTeclado
from capture.clasificador_cli import agrupar_evidencia_por_dispositivo
from ui.ventanas_tk import InterfazFases


class OrquestadorAgente:
    def __init__(self) -> None:
        inicializar_directorios_locales()

        if hosts_estan_bloqueados() and es_administrador():
            restaurar_hosts()

        self.mac_estacion = obtener_mac_principal()
        self.recolector = RecolectorTeclado(solo_ventanas_pt=True)
        self.app = InterfazFases(mac_estacion=self.mac_estacion)
        self.token_actual: str = ""
        self.app.protocol("WM_DELETE_WINDOW", self._al_cerrar_aplicacion)

        if not self.mac_estacion:
            messagebox.showwarning(
                "EVIDENS",
                "No se pudo identificar la tarjeta de red de esta estación.\n"
                "El servidor podría rechazar el registro.",
            )

    def iniciar(self) -> None:
        self.app.mostrar_fase_token(al_validar=self._procesar_token)
        self.app.mainloop()

    def _procesar_token(self, token: str) -> None:
        self.token_actual = token
        datos_vlsm = {
            "token": token,
            "estacion_mac": self.mac_estacion,
            "detalles": (
                f"Token registrado: {token}\n"
                f"Dirección MAC: {self.mac_estacion or '(no detectada)'}\n\n"
                "Red asignada: 192.168.10.0/24\n"
                "- Subred A (LAN Servidores): 60 hosts\n"
                "- Subred B (LAN Docencia): 30 hosts\n"
                "- Subred C (LAN Enlace WAN): 2 hosts\n\n"
                "Realice el cálculo en su hoja o herramienta autorizada."
            ),
        }
        self.app.mostrar_fase_vlsm(
            datos_vlsm=datos_vlsm,
            al_reintentar_check=self._verificar_habilitacion_docente,
        )

    def _verificar_habilitacion_docente(self) -> None:
        if not es_administrador():
            messagebox.showerror(
                "EVIDENS - Permisos insuficientes",
                "El cliente debe ejecutarse como Administrador para aplicar el bloqueo de red.\n"
                "Cierre la aplicación y vuelva a abrirla con 'Ejecutar como administrador'.",
            )
            return

        if not aplicar_bloqueo():
            messagebox.showwarning(
                "EVIDENS - Bloqueo de red",
                "No se pudo aplicar el bloqueo de dominios.\n"
                "El examen continuará, pero el docente debe verificar el archivo hosts.",
            )

        if not self.recolector.iniciar():
            messagebox.showerror(
                "EVIDENS - Captura",
                "No se pudo iniciar el recolector de teclado. Contacte al docente.",
            )
            return

        instrucciones = (
            "1. Abra Cisco Packet Tracer y configure la topología según VLSM asignado.\n"
            "2. Asigne direccionamiento IP, máscaras y gateways correspondientes.\n"
            "3. Verifique conectividad extremo a extremo con comandos ping.\n"
            "4. No cierre esta ventana durante el desarrollo del examen."
        )
        self.app.mostrar_fase_examen(
            duracion_segundos=5400,
            instrucciones=instrucciones,
            al_finalizar=self._finalizar_examen,
        )

    def _finalizar_examen(self) -> None:
        self.recolector.detener()
        restaurar_hosts()

        eventos = self.recolector.extraer_eventos()
        evidencia_clasificada = agrupar_evidencia_por_dispositivo(eventos)

        archivo_log = EVIDENS_TEMP_DIR / f"keylog_{self.token_actual}_{int(time.time())}.json"
        try:
            with open(archivo_log, "w", encoding="utf-8") as f:
                json.dump(evidencia_clasificada, f, indent=2, ensure_ascii=False)
            total_cmds = sum(len(v) for v in evidencia_clasificada["dispositivos"].values())
            mensaje = (
                f"Examen finalizado con éxito.\n"
                f"Dispositivos detectados: {len(evidencia_clasificada['dispositivos'])}\n"
                f"Comandos registrados: {total_cmds}\n"
                f"Archivo listo para transferencia: {archivo_log.name}"
            )
            self.app.mostrar_fase_finalizacion(mensaje=mensaje, completado=True)
        except OSError as exc:
            self.app.mostrar_fase_finalizacion(
                mensaje=f"Examen finalizado con advertencias al guardar evidencia: {exc}",
                completado=False,
            )

    def _al_cerrar_aplicacion(self) -> None:
        self.recolector.detener()
        if es_administrador():
            restaurar_hosts()
        self.app.destroy()


def main() -> None:
    try:
        OrquestadorAgente().iniciar()
    finally:
        if es_administrador():
            restaurar_hosts()


if __name__ == "__main__":
    main()