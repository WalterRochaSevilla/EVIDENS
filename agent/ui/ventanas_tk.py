"""Interfaz gráfica con identidad propia en barra de tareas y temporizador flotante."""

import ctypes, os, time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable

from core.configuracion import APP_NAME, APP_USER_MODEL_ID, obtener_ruta_icono
from ui.temporizador_flotante import TemporizadorFlotante, abrir_dialogo_control_docente


class InterfazFases(tk.Tk):
    """Ventana principal de EVIDENS con soporte de minimizado a esquina flotante."""

    def __init__(self, mac_estacion: str = "") -> None:
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
        except Exception:
            pass
        super().__init__()
        self.mac_estacion = mac_estacion
        self.title(APP_NAME)
        self.geometry("640x480")
        self.minsize(580, 440)
        self.configure(bg="#f4f6f9")
        ruta_ico = obtener_ruta_icono()
        if ruta_ico:
            try:
                self.iconbitmap(default=str(ruta_ico))
            except Exception:
                pass
        self._hora_fin: float = 0.0
        self._al_finalizar_examen = self._al_habilitar_demo = self._al_forzar_salida = None
        self._entrega_en_curso, self._modal_abierto = False, False
        self.examen_activo, self.en_espera_vlsm = False, False
        self._lbl_timer = self._lbl_alertas = self._lbl_clips = None
        self._flotante: TemporizadorFlotante | None = None
        self._construir_encabezado()
        self.contenedor = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        self.contenedor.pack(fill="both", expand=True, padx=18, pady=12)
        self.bind_all("<KeyPress>", self._detectar_atajo_teclado)
        self.bind_all("<F12>", lambda _e: self._abrir_panel_docente())

    @property
    def hora_fin(self) -> float:
        return self._hora_fin

    @property
    def tiempo_restante_segundos(self) -> int:
        return max(0, int(self._hora_fin - time.time()))

    def configurar_salida_forzada(self, callback: Callable[[], None]) -> None:
        self._al_forzar_salida = callback

    def ajustar_tiempo(self, delta: int) -> None:
        self._hora_fin += delta
        self._refrescar_etiquetas_tiempo()

    def _construir_encabezado(self) -> None:
        enc = tk.Frame(self, bg="#1a365d", height=44)
        enc.pack(fill="x", side="top")
        tk.Label(enc, text="🛡 EVIDENS", fg="#ffffff", bg="#1a365d", font=("Segoe UI", 13, "bold")).pack(side="left", padx=15, pady=6)
        tk.Label(enc, text=f"MAC: {self.mac_estacion or 'No detectada'}", fg="#cbd5e1", bg="#1a365d", font=("Consolas", 9)).pack(side="right", padx=15, pady=8)

    def _destruir_flotante(self) -> None:
        if self._flotante is not None:
            try:
                self._flotante.destroy()
            except Exception:
                pass
            self._flotante = None

    def _limpiar_contenedor(self) -> None:
        self._destruir_flotante()
        self._al_finalizar_examen, self._al_habilitar_demo = None, None
        self._entrega_en_curso, self.examen_activo, self.en_espera_vlsm = False, False, False
        for widget in self.contenedor.winfo_children():
            widget.destroy()

    def mostrar_fase_token(self, al_validar: Callable[[str, str], None]) -> None:
        self._limpiar_contenedor()
        tk.Label(self.contenedor, text="Registro de Estación y Token", font=("Segoe UI", 13, "bold"), bg="#ffffff", fg="#2d3748").pack(pady=(25, 15))
        tk.Label(self.contenedor, text="Nombre completo del estudiante:", font=("Segoe UI", 10), bg="#ffffff", fg="#4a5568").pack(pady=(5, 3))
        entrada_nombre = ttk.Entry(self.contenedor, font=("Segoe UI", 11), width=36)
        entrada_nombre.pack(pady=4, ipady=3)
        entrada_nombre.focus()
        tk.Label(self.contenedor, text="Código de acceso (Token):", font=("Segoe UI", 10), bg="#ffffff", fg="#4a5568").pack(pady=(12, 3))
        entrada_token = ttk.Entry(self.contenedor, font=("Consolas", 13), justify="center", width=18)
        entrada_token.pack(pady=4, ipady=3)

        def _enviar() -> None:
            nombre, token = entrada_nombre.get().strip(), entrada_token.get().strip()
            if not nombre or not token:
                messagebox.showwarning("Atención", "Complete su nombre y el código de acceso.")
                return
            al_validar(nombre, token)

        tk.Button(self.contenedor, text="Validar y Continuar", bg="#2b6cb0", fg="#ffffff", font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=7, command=_enviar).pack(pady=22)

    def mostrar_fase_vlsm(self, datos_vlsm: dict[str, Any], al_habilitar: Callable[[], None]) -> None:
        self._limpiar_contenedor()
        self.en_espera_vlsm, self._al_habilitar_demo = True, al_habilitar
        tk.Label(self.contenedor, text="Requerimientos de Subneteo (VLSM)", font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#2d3748").pack(pady=(14, 4))
        txt_info = tk.Text(self.contenedor, height=11, font=("Consolas", 9), relief="solid", bd=1)
        txt_info.pack(fill="both", expand=True, padx=20, pady=8)
        txt_info.insert("1.0", str(datos_vlsm.get("detalles", "")))
        txt_info.configure(state="disabled")
        tk.Label(self.contenedor, text="⏳ Esperando habilitación del docente desde el servidor...", font=("Segoe UI", 10, "italic"), bg="#ffffff", fg="#d69e2e").pack(pady=14)

    def mostrar_fase_examen(self, hora_fin: float, instrucciones: str, carpeta_trabajo: Path, al_finalizar: Callable[[str], None]) -> None:
        self._limpiar_contenedor()
        self.examen_activo, self._hora_fin, self._al_finalizar_examen = True, float(hora_fin), al_finalizar
        barra = tk.Frame(self.contenedor, bg="#edf2f7", padx=12, pady=6)
        barra.pack(fill="x", padx=15, pady=(12, 6))
        tk.Label(barra, text="● Monitoreo, Búfer de Video y Cortafuegos Activos", font=("Segoe UI", 9, "bold"), bg="#edf2f7", fg="#2f855a").pack(side="left")
        self._lbl_timer = tk.Label(barra, text=f"Tiempo: {self._formatear_tiempo(self.tiempo_restante_segundos)}", font=("Consolas", 12, "bold"), bg="#edf2f7", fg="#c53030")
        self._lbl_timer.pack(side="right")

        metricas = tk.Frame(self.contenedor, bg="#ffffff")
        metricas.pack(fill="x", padx=16, pady=(0, 4))
        self._lbl_alertas = tk.Label(metricas, text="Alertas registradas: 0", font=("Segoe UI", 9), bg="#ffffff", fg="#718096")
        self._lbl_alertas.pack(side="left")
        self._lbl_clips = tk.Label(metricas, text="Clips de video: 0", font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2b6cb0")
        self._lbl_clips.pack(side="right")

        txt = tk.Text(self.contenedor, height=9, font=("Segoe UI", 9), relief="solid", bd=1)
        txt.pack(fill="both", expand=True, padx=15, pady=6)
        txt.insert("1.0", instrucciones)
        txt.configure(state="disabled")

        pie = tk.Frame(self.contenedor, bg="#ffffff")
        pie.pack(fill="x", padx=15, pady=8)
        tk.Button(pie, text="🗕 Minimizar a Esquina", bg="#1e3a8a", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, command=self.iconify).pack(side="left")
        tk.Button(pie, text="📂 Abrir Carpeta trabajo/", bg="#2b6cb0", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", padx=10, pady=4, command=lambda: os.startfile(str(carpeta_trabajo))).pack(side="right")

        self._flotante = TemporizadorFlotante(self, carpeta_trabajo, self._restaurar_ventana, self._abrir_panel_docente)
        self._refrescar_etiquetas_tiempo()
        self.after(1200, self.iconify)

    def _restaurar_ventana(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _detectar_atajo_teclado(self, event: Any) -> None:
        if (getattr(event, "state", 0) & 0x4) and getattr(event, "keycode", 0) == 68:
            self._abrir_panel_docente()

    def _abrir_panel_docente(self) -> None:
        if self._modal_abierto or (not self.en_espera_vlsm and not self.examen_activo):
            return
        self._modal_abierto = True
        padre = self._flotante if (self._flotante and self._flotante.winfo_exists()) else self
        try:
            abrir_dialogo_control_docente(self, padre, self.en_espera_vlsm, self.examen_activo, self._al_habilitar_demo, self._al_forzar_salida, self.ajustar_tiempo, self.disparar_finalizacion)
        finally:
            self._modal_abierto = False

    def _refrescar_etiquetas_tiempo(self) -> None:
        restante = self.tiempo_restante_segundos
        txt = self._formatear_tiempo(restante)
        if self._lbl_timer and self._lbl_timer.winfo_exists():
            self._lbl_timer.configure(text=f"Tiempo: {txt}")
        if self._flotante:
            self._flotante.actualizar_reloj(txt, pocos_minutos=(restante < 600))

    def actualizar_estado_supervision(self, total_alertas: int, total_clips: int, ultima_alerta: str = "") -> None:
        if self._lbl_alertas and self._lbl_alertas.winfo_exists() and ultima_alerta:
            self._lbl_alertas.configure(text=f"⚠ Alertas ({total_alertas}): {ultima_alerta[:38]}", fg="#c53030", font=("Segoe UI", 9, "bold"))
        if self._lbl_clips and self._lbl_clips.winfo_exists():
            self._lbl_clips.configure(text=f"Clips de video: {total_clips}")
        if self._flotante:
            self._flotante.actualizar_metricas(total_alertas, total_clips)

    def avanzar_un_segundo(self) -> None:
        if not self.examen_activo:
            return
        self._refrescar_etiquetas_tiempo()
        if self.tiempo_restante_segundos <= 0:
            self.disparar_finalizacion("TIEMPO_AGOTADO")

    def disparar_finalizacion(self, motivo_cierre: str = "TIEMPO_AGOTADO") -> None:
        if self._entrega_en_curso:
            return
        self._entrega_en_curso, self.examen_activo = True, False
        if self._al_finalizar_examen:
            self._al_finalizar_examen(motivo_cierre)

    def mostrar_fase_finalizacion(self, mensaje: str, ruta_carpeta: Path | None = None, completado: bool = True, al_cerrar: Callable[[], None] | None = None) -> None:
        self._limpiar_contenedor()
        self._restaurar_ventana()
        tk.Label(self.contenedor, text=mensaje, font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2f855a" if completado else "#c53030", wraplength=540, justify="left").pack(pady=(22, 12), padx=20)
        if ruta_carpeta is not None and ruta_carpeta.exists():
            tk.Button(self.contenedor, text="📂 Abrir Carpeta de Evidencias (.zip)", bg="#2b6cb0", fg="#ffffff", font=("Segoe UI", 9, "bold"), relief="flat", padx=12, pady=6, command=lambda: os.startfile(str(ruta_carpeta))).pack(pady=6)
        tk.Button(self.contenedor, text="Salir", bg="#4a5568", fg="#ffffff", font=("Segoe UI", 10), relief="flat", padx=18, pady=5, command=al_cerrar if al_cerrar else self.destroy).pack(pady=10)

    @staticmethod
    def _formatear_tiempo(total_segundos: int) -> str:
        return f"{total_segundos // 3600:02d}:{(total_segundos % 3600) // 60:02d}:{total_segundos % 60:02d}"
