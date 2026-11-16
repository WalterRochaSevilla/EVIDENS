import json
import sys
import time
from pathlib import Path
from tkinter import messagebox

directorio_actual = Path(__file__).resolve().parent
if str(directorio_actual) not in sys.path:
    sys.path.insert(0, str(directorio_actual))

from capture.clasificador_cli import agrupar_evidencia_por_dispositivo
from capture.recolector_teclado import RecolectorTeclado
from control.administrador_hosts import (
    aplicar_bloqueo,
    es_administrador,
    hosts_estan_bloqueados,
    relanzar_como_administrador,
    restaurar_hosts,
)
from control.validador_mac import obtener_mac_principal
from core.configuracion import EVIDENS_TEMP_DIR, inicializar_directorios_locales
from ui.ventanas_tk import InterfazFases


class OrquestadorAgente:
    def __init__(self) -> None:
        inicializar_directorios_locales()
        if hosts_estan_bloqueados() and es_administrador():
            restaurar_hosts()

        self.mac_estacion = obtener_mac_principal()
        self.app = InterfazFases(mac_estacion=self.mac_estacion)
        self.recolector = RecolectorTeclado(al_detectar_alerta=self._notificar_alerta_ui)
        self.nombre_estudiante: str = ""
        self.token_actual: str = ""
        self.app.protocol("WM_DELETE_WINDOW", self._al_intentar_cerrar_ventana)

    def _notificar_alerta_ui(self, termino: str, ventana: str) -> None:
        self.app.after(0, lambda: self.app.notificar_alerta_visual(termino, ventana))

    def iniciar(self) -> None:
        self.app.mostrar_fase_token(al_validar=self._procesar_registro_inicial)
        self.app.mainloop()

    def _procesar_registro_inicial(self, nombre: str, token: str) -> None:
        self.nombre_estudiante = nombre
        self.token_actual = token
        datos_vlsm = {
            "token": token,
            "estudiante": nombre,
            "estacion_mac": self.mac_estacion,
            "detalles": (
                f"Estudiante : {nombre}\n"
                f"Token      : {token}\n"
                f"MAC Equipo : {self.mac_estacion or '(no detectada)'}\n\n"
                "Red asignada: 192.168.10.0/24\n"
                "- Subred A (LAN Servidores): 60 hosts\n"
                "- Subred B (LAN Docencia): 30 hosts\n"
                "- Subred C (LAN Enlace WAN): 2 hosts\n\n"
                "Realice el cálculo en su hoja. Una vez validado por el docente, inicie el examen."
            ),
        }
        self.app.mostrar_fase_vlsm(
            datos_vlsm=datos_vlsm,
            al_reintentar_check=self._verificar_habilitacion_docente,
        )

    def _verificar_habilitacion_docente(self) -> None:
        if not aplicar_bloqueo():
            messagebox.showwarning(
                "EVIDENS - Bloqueo de red",
                "No se pudo escribir en el archivo hosts (ejecute con permisos de Administrador).",
            )

        self.recolector.iniciar()
        instrucciones = (
            "1. Abra Cisco Packet Tracer y configure la topología según el VLSM asignado.\n"
            "2. Asigne nombres de dispositivo (hostname), direcciones IP y máscaras.\n"
            "3. Verifique conectividad extremo a extremo con comandos ping.\n"
            "4. El cierre de esta ventana está bloqueado hasta presionar 'Entregar Examen'."
        )
        self.app.mostrar_fase_examen(
            duracion_segundos=5400,
            instrucciones=instrucciones,
            al_finalizar=self._finalizar_examen,
        )

    def _finalizar_examen(self) -> None:
        self.recolector.detener()
        if es_administrador():
            restaurar_hosts()

        eventos, alertas_ventana = self.recolector.extraer_datos()
        evidencia = agrupar_evidencia_por_dispositivo(eventos, alertas_ventana)
        evidencia["metadata"] = {
            "estudiante": self.nombre_estudiante,
            "token": self.token_actual,
            "station_mac": self.mac_estacion,
            "fecha_entrega": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        archivo_log = EVIDENS_TEMP_DIR / f"keylog_{self.token_actual}_{int(time.time())}.json"
        try:
            archivo_log.write_text(
                json.dumps(evidencia, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            total_cmds = sum(len(v) for v in evidencia["dispositivos"].values())
            mensaje = (
                f"Examen finalizado con éxito.\n\n"
                f"• Estudiante: {self.nombre_estudiante} (Token: {self.token_actual})\n"
                f"• Dispositivos PT detectados: {len(evidencia['dispositivos'])}\n"
                f"• Comandos CLI registrados: {total_cmds}\n"
                f"• Eventos Ctrl+C / Ctrl+V: {len(evidencia['eventos_portapapeles'])}\n"
                f"• Alertas de ventana (IA/Web): {len(evidencia['alertas_intencion_ventana'])}\n\n"
                f"Guardado en:\n{archivo_log}"
            )
            self.app.mostrar_fase_finalizacion(
                mensaje=mensaje,
                ruta_archivo=archivo_log,
                completado=True,
                al_cerrar=self._cerrar_definitivamente,
            )
        except OSError as exc:
            self.app.mostrar_fase_finalizacion(
                mensaje=f"Error al guardar evidencia: {exc}",
                completado=False,
                al_cerrar=self._cerrar_definitivamente,
            )

    def _al_intentar_cerrar_ventana(self) -> None:
        if self.app.examen_activo:
            messagebox.showwarning(
                "Examen en curso",
                "No puede cerrar la aplicación durante el examen.\n"
                "Utilice el botón 'Entregar Examen' cuando haya concluido.",
            )
            return
        self._cerrar_definitivamente()

    def _cerrar_definitivamente(self) -> None:
        self.recolector.detener()
        if es_administrador():
            restaurar_hosts()
        self.app.destroy()


def main() -> None:
    if not es_administrador():
        if relanzar_como_administrador():
            sys.exit(0)
    try:
        OrquestadorAgente().iniciar()
    finally:
        if es_administrador():
            restaurar_hosts()


if __name__ == "__main__":
    main()