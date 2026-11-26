"""Punto de entrada principal del cliente portable EVIDENS con recuperación y monitoreo."""

import atexit, faulthandler, os, sys, time
from pathlib import Path
from tkinter import messagebox
from typing import Any

directorio_actual = Path(__file__).resolve().parent
if str(directorio_actual) not in sys.path:
    sys.path.insert(0, str(directorio_actual))

from capture.buffer_video import BufferCircularVideo
from capture.recolector_teclado import RecolectorTeclado, evaluar_alerta_entorno, obtener_hwnd_activo, obtener_proceso_de_ventana, obtener_titulo_ventana
from control.administrador_hosts import aplicar_bloqueo, es_administrador, hosts_estan_bloqueados, relanzar_como_administrador, restaurar_hosts
from control.monitor_procesos import MonitorProcesosRemotos
from control.monitor_usb import MonitorUSB
from control.validador_mac import obtener_mac_principal
from core.configuracion import BUFFER_VIDEO_SECONDS, CHECKPOINT_INTERVAL_SEC, SERVER_POLL_INTERVAL_SEC, obtener_directorio_base_evidencias
from core.recuperacion import anexar_eventos_jsonl, calcular_rutas_estudiante, cargar_sesion_interrumpida, consolidar_y_empaquetar_entrega, consultar_orden_servidor, guardar_checkpoint_estado, limpiar_marca_sesion_activa, listar_archivos_pkt, preparar_carpetas_estudiante
from ui.ventanas_tk import InterfazFases


class OrquestadorAgente:
    """Coordina la interfaz, el búfer de video, cronología de ventanas, USB y checkpoints."""

    def __init__(self) -> None:
        self.mac_estacion = obtener_mac_principal()
        self.app = InterfazFases(mac_estacion=self.mac_estacion)
        self.recolector = RecolectorTeclado()
        self.buffer_video = BufferCircularVideo(max_cuadros=BUFFER_VIDEO_SECONDS)
        self.monitor_usb, self.monitor_remotos = MonitorUSB(), MonitorProcesosRemotos()
        self.nombre_estudiante, self.token_actual = "", ""
        self.carpeta_estudiante, self.carpeta_trabajo = Path("."), Path(".")
        self.alertas_ventana: list[dict[str, Any]] = []
        self.historial_ventanas: list[dict[str, Any]] = []
        self.cierres_forzados: list[str] = []
        self._ultima_alerta_key, self._ticks_transcurridos = "", 0
        self.app.configurar_salida_forzada(self._salir); self.app.protocol("WM_DELETE_WINDOW", self._al_intentar_cerrar_ventana)

    def iniciar(self) -> None:
        sesion_previa = cargar_sesion_interrumpida()
        if sesion_previa:
            self._recuperar_sesion_interrumpida(sesion_previa)
        else:
            if hosts_estan_bloqueados() and es_administrador():
                restaurar_hosts()
            self.app.mostrar_fase_token(al_validar=self._procesar_registro_inicial)
        self.app.mainloop()

    def _registrar_alerta(self, motivo: str, ventana: str, proceso: str, volcar: bool = True) -> None:
        clip = self.buffer_video.volcar_clip(self.carpeta_estudiante / "clips", motivo) if volcar else None
        self.alertas_ventana.append({"timestamp": round(time.time(), 2), "hora": time.strftime("%H:%M:%S"), "termino_detectado": motivo, "ventana": ventana, "proceso": proceso, "clip_evidencia": clip or "sin_clip"})

    def _registrar_ventana_activa(self, titulo: str, proceso: str) -> None:
        if not titulo and not proceso:
            return
        if self.historial_ventanas and self.historial_ventanas[-1]["ventana"] == titulo and self.historial_ventanas[-1]["proceso"] == proceso:
            self.historial_ventanas[-1]["duracion_seg"] += 1
        else:
            self.historial_ventanas.append({"timestamp": round(time.time(), 2), "hora": time.strftime("%H:%M:%S"), "ventana": titulo or "(Sin título)", "proceso": proceso or "desconocido", "duracion_seg": 1})

    def _recuperar_sesion_interrumpida(self, sesion: dict[str, Any]) -> None:
        self.nombre_estudiante, self.token_actual = str(sesion.get("estudiante", "Estudiante")), str(sesion.get("token", "REC"))
        self.carpeta_estudiante, self.carpeta_trabajo, _ = preparar_carpetas_estudiante(self.nombre_estudiante)
        self.alertas_ventana, self.historial_ventanas = list(sesion.get("alertas_ventana", [])), list(sesion.get("historial_ventanas", []))
        self.buffer_video.clips_generados, self.cierres_forzados = list(sesion.get("clips", [])), list(sesion.get("cierres_forzados", []))
        self.cierres_forzados.append(f"Recuperación tras cierre abrupto ({time.strftime('%H:%M:%S')})")
        self._registrar_alerta("CIERRE_FORZADO_O_APAGON", "Sistema", "recuperacion", volcar=False)
        self._arrancar_examen_con_hora_fin(float(sesion.get("hora_fin", time.time() + 1800)), es_recuperacion=True)

    def _procesar_registro_inicial(self, nombre: str, token: str) -> None:
        self.nombre_estudiante, self.token_actual = nombre, token
        self.carpeta_estudiante, self.carpeta_trabajo = calcular_rutas_estudiante(nombre)
        detalles = f"Estudiante : {nombre}\nMAC Equipo : {self.mac_estacion}\nCarpeta .pkt: {self.carpeta_trabajo}\n\nRed asignada: 192.168.10.0/24\n- Subred A (LAN Servidores): 60 hosts\n- Subred B (LAN Docencia): 30 hosts\n- Subred C (LAN Enlace WAN): 2 hosts"
        self.app.mostrar_fase_vlsm({"detalles": detalles}, lambda: self._arrancar_examen_con_hora_fin(time.time() + 5400))
        self.app.after(SERVER_POLL_INTERVAL_SEC * 1000, self._sondear_habilitacion_vlsm)

    def _sondear_habilitacion_vlsm(self) -> None:
        if not self.app.en_espera_vlsm:
            return
        orden = consultar_orden_servidor(self.token_actual, self.mac_estacion)
        if orden and orden.get("habilitado"):
            self._arrancar_examen_con_hora_fin(time.time() + int(orden.get("duracion_segundos", 5400))); return
        self.app.after(SERVER_POLL_INTERVAL_SEC * 1000, self._sondear_habilitacion_vlsm)

    def _arrancar_examen_con_hora_fin(self, hora_fin: float, es_recuperacion: bool = False) -> None:
        self.carpeta_estudiante, self.carpeta_trabajo, ruta_pkt = preparar_carpetas_estudiante(self.nombre_estudiante)
        self.monitor_usb.reiniciar_base(); self.monitor_remotos.reiniciar()
        if not aplicar_bloqueo():
            self._registrar_alerta("BLOQUEO_NO_APLICADO", "hosts", "sistema", volcar=False)
        if not es_recuperacion:
            try:
                os.startfile(str(ruta_pkt if ruta_pkt else self.carpeta_trabajo))
            except OSError:
                pass
        self.recolector.iniciar()
        aviso = "⚠ SESIÓN RECUPERADA TRAS CIERRE INESPERADO.\n\n" if es_recuperacion else ""
        instrucciones = f"{aviso}1. OBLIGATORIO: Guarde su archivo .pkt dentro de:\n   {self.carpeta_trabajo}\n2. Configure los dispositivos en Cisco Packet Tracer según el VLSM asignado.\n3. No abra Bloc de notas, navegadores ni memorias USB durante la evaluación."
        self.app.mostrar_fase_examen(hora_fin, instrucciones, self.carpeta_trabajo, self._finalizar_examen)
        self._guardar_checkpoint("EN_CURSO")
        self._ciclo_supervision_principal()

    def _ciclo_supervision_principal(self) -> None:
        if not self.app.examen_activo:
            return
        self.app.avanzar_un_segundo()
        if not self.app.examen_activo:
            return
        self.buffer_video.capturar_cuadro(); self._resolver_portapapeles_seguro()
        alerta_txt = self._inspeccionar_entorno_y_usb(); self._ticks_transcurridos += 1
        if self._ticks_transcurridos % CHECKPOINT_INTERVAL_SEC == 0:
            self._guardar_checkpoint("EN_CURSO")
        if self._ticks_transcurridos % SERVER_POLL_INTERVAL_SEC == 0:
            self._procesar_ordenes_remotas()
        self.app.actualizar_estado_supervision(len(self.alertas_ventana), len(self.buffer_video.clips_generados), alerta_txt)
        self.app.after(1000, self._ciclo_supervision_principal)

    def _resolver_portapapeles_seguro(self) -> None:
        if not self.recolector.hay_portapapeles_pendiente():
            return
        try:
            texto = str(self.app.clipboard_get())[:400]
        except Exception:
            texto = ""
        for alerta in self.recolector.resolver_portapapeles_en_hilo_principal(texto):
            self._registrar_alerta("PEGADO_DESDE_ORIGEN_EXTERNO", f"{alerta['ventana_origen']} -> {alerta['ventana_destino']}", alerta["proceso_origen"])

    def _inspeccionar_entorno_y_usb(self) -> str:
        ultima = ""
        for unidad in self.monitor_usb.detectar_nuevas_unidades():
            self._registrar_alerta("USB_CONECTADO", f"Unidad {unidad}", "explorador"); ultima = f"USB_CONECTADO ({unidad})"
        for alerta_ram in self.recolector.extraer_alertas_intencion_ram():
            self._registrar_alerta(alerta_ram["categoria"], alerta_ram["ventana"], alerta_ram["proceso"]); ultima = f"{alerta_ram['categoria']} ({alerta_ram['proceso']})"
        if self._ticks_transcurridos % 4 == 0:
            for etiqueta, proc in self.monitor_remotos.detectar_procesos_prohibidos():
                self._registrar_alerta(etiqueta, "Proceso en segundo plano", proc); ultima = f"{etiqueta} ({proc})"
        hwnd = obtener_hwnd_activo()
        titulo, proceso = obtener_titulo_ventana(hwnd), obtener_proceso_de_ventana(hwnd)
        self._registrar_ventana_activa(titulo, proceso)
        motivo = evaluar_alerta_entorno(titulo, proceso)
        if not motivo:
            self._ultima_alerta_key = ""; return ultima
        if f"{motivo}:{titulo}" != self._ultima_alerta_key:
            self._ultima_alerta_key = f"{motivo}:{titulo}"
            self._registrar_alerta(motivo, titulo, proceso); self._guardar_checkpoint("EN_CURSO")
        return f"{motivo} ({proceso})"

    def _procesar_ordenes_remotas(self) -> None:
        orden = consultar_orden_servidor(self.token_actual, self.mac_estacion)
        if not orden:
            return
        if orden.get("delta_segundos"):
            self.app.ajustar_tiempo(int(orden["delta_segundos"]))
        estado = str(orden.get("accion", "")).upper()
        if estado in ("FINALIZADO_POR_DOCENTE", "ANULADO_POR_DOCENTE"):
            self.app.disparar_finalizacion(estado)

    def _guardar_checkpoint(self, estado_cierre: str) -> None:
        anexar_eventos_jsonl(self.carpeta_estudiante, self.recolector.extraer_eventos_nuevos())
        guardar_checkpoint_estado({"estado": estado_cierre, "estudiante": self.nombre_estudiante, "token": self.token_actual, "carpeta_salida": str(self.carpeta_estudiante), "hora_fin": self.app.hora_fin, "alertas_ventana": self.alertas_ventana, "historial_ventanas": self.historial_ventanas, "clips": self.buffer_video.clips_generados, "cierres_forzados": self.cierres_forzados})

    def _finalizar_examen(self, motivo_cierre: str = "FINALIZADO") -> None:
        self.recolector.detener(); restaurar_hosts(); self._resolver_portapapeles_seguro()
        archivos_pkt = listar_archivos_pkt(self.carpeta_estudiante)
        if not archivos_pkt:
            self._registrar_alerta("SIN_PKT", str(self.carpeta_trabajo), "verificador_pkt", volcar=False)
        self._guardar_checkpoint(motivo_cierre); limpiar_marca_sesion_activa()
        msg = consolidar_y_empaquetar_entrega(self.carpeta_estudiante, self.nombre_estudiante, self.token_actual, self.mac_estacion, motivo_cierre, self.alertas_ventana, self.historial_ventanas, self.buffer_video.clips_generados, self.cierres_forzados, archivos_pkt)
        self.app.mostrar_fase_finalizacion(msg, self.carpeta_estudiante, motivo_cierre != "ANULADO_POR_DOCENTE", self._salir)

    def _al_intentar_cerrar_ventana(self) -> None:
        if self.app.examen_activo or self.app.en_espera_vlsm:
            if self.app.examen_activo:
                self._registrar_alerta("INTENTO_CIERRE_VENTANA", "EVIDENS", Path(sys.executable).name)
                self._guardar_checkpoint("EN_CURSO")
            messagebox.showwarning("Acción Bloqueada", "El cierre está bloqueado durante la sesión de examen.")
            return
        self._salir()

    def _salir(self) -> None:
        self.recolector.detener(); restaurar_hosts(); self.app.destroy()


def main() -> None:
    try:
        faulthandler.enable(open(obtener_directorio_base_evidencias() / "fallos.log", "a", encoding="utf-8"))
    except Exception:
        pass
    if "--desbloquear" in sys.argv:
        if not es_administrador() and relanzar_como_administrador():
            sys.exit(0)
        restaurar_hosts(); limpiar_marca_sesion_activa(); sys.exit(0)
    if not es_administrador() and relanzar_como_administrador():
        sys.exit(0)
    atexit.register(restaurar_hosts)
    OrquestadorAgente().iniciar()

if __name__ == "__main__":
    main()
