import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable


class InterfazFases(tk.Tk):
    def __init__(self, mac_estacion: str = "") -> None:
        super().__init__()
        self.mac_estacion = mac_estacion
        self.title("EVIDENS - Cliente de Examen")
        self.geometry("620x460")
        self.minsize(560, 420)
        self.configure(bg="#f4f6f9")

        self._tiempo_restante_segundos = 0
        self._timer_id: str | None = None
        self._al_finalizar_examen: Callable[[], None] | None = None
        self._entrega_en_curso = False
        self.examen_activo = False
        self._lbl_alertas: tk.Label | None = None
        self._contador_alertas = 0

        self._construir_encabezado()
        self.contenedor = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        self.contenedor.pack(fill="both", expand=True, padx=18, pady=12)

    def _construir_encabezado(self) -> None:
        encabezado = tk.Frame(self, bg="#1a365d", height=44)
        encabezado.pack(fill="x", side="top")
        tk.Label(
            encabezado, text="EVIDENS", fg="#ffffff", bg="#1a365d",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left", padx=15, pady=6)
        tk.Label(
            encabezado,
            text=f"MAC: {self.mac_estacion or 'No detectada'}",
            fg="#cbd5e1", bg="#1a365d", font=("Consolas", 9),
        ).pack(side="right", padx=15, pady=8)

    def _detener_cronometro(self) -> None:
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except tk.TclError:
                pass
            self._timer_id = None

    def _limpiar_contenedor(self) -> None:
        self._detener_cronometro()
        self._al_finalizar_examen = None
        self._entrega_en_curso = False
        self.examen_activo = False
        for widget in self.contenedor.winfo_children():
            widget.destroy()

    def mostrar_fase_token(self, al_validar: Callable[[str, str], None]) -> None:
        self._limpiar_contenedor()
        tk.Label(
            self.contenedor, text="Registro de Estación y Token",
            font=("Segoe UI", 13, "bold"), bg="#ffffff", fg="#2d3748",
        ).pack(pady=(25, 15))

        tk.Label(
            self.contenedor, text="Nombre completo del estudiante:",
            font=("Segoe UI", 10), bg="#ffffff", fg="#4a5568",
        ).pack(pady=(5, 3))
        entrada_nombre = ttk.Entry(self.contenedor, font=("Segoe UI", 11), width=36)
        entrada_nombre.pack(pady=4, ipady=3)
        entrada_nombre.focus()

        tk.Label(
            self.contenedor, text="Código de acceso (Token de la sesión):",
            font=("Segoe UI", 10), bg="#ffffff", fg="#4a5568",
        ).pack(pady=(12, 3))
        entrada_token = ttk.Entry(self.contenedor, font=("Consolas", 13), justify="center", width=18)
        entrada_token.pack(pady=4, ipady=3)

        def _enviar() -> None:
            nombre = entrada_nombre.get().strip()
            token = entrada_token.get().strip()
            if not nombre or not token:
                messagebox.showwarning("Atención", "Complete su nombre y el código de acceso.")
                return
            al_validar(nombre, token)

        tk.Button(
            self.contenedor, text="Validar y Continuar", bg="#2b6cb0", fg="#ffffff",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=16, pady=7,
            command=_enviar,
        ).pack(pady=22)

    def mostrar_fase_vlsm(
        self, datos_vlsm: dict[str, Any], al_reintentar_check: Callable[[], None]
    ) -> None:
        self._limpiar_contenedor()
        tk.Label(
            self.contenedor, text="Requerimientos de Subneteo (VLSM)",
            font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#2d3748",
        ).pack(pady=(12, 4))

        txt_info = tk.Text(self.contenedor, height=10, font=("Consolas", 9), relief="solid", bd=1)
        txt_info.pack(fill="both", expand=True, padx=20, pady=8)
        txt_info.insert("1.0", str(datos_vlsm.get("detalles", "Sin requerimientos asignados")))
        txt_info.configure(state="disabled")

        tk.Label(
            self.contenedor,
            text="Esperando validación manual del docente para desbloquear instrucciones...",
            font=("Segoe UI", 9, "italic"), bg="#ffffff", fg="#d69e2e",
        ).pack(pady=4)

        tk.Button(
            self.contenedor, text="Habilitar e Iniciar Examen",
            bg="#2f855a", fg="#ffffff", font=("Segoe UI", 10, "bold"),
            relief="flat", padx=12, pady=6, command=al_reintentar_check,
        ).pack(pady=10)

    def mostrar_fase_examen(
        self, duracion_segundos: int, instrucciones: str, al_finalizar: Callable[[], None]
    ) -> None:
        self._limpiar_contenedor()
        self.examen_activo = True
        self._contador_alertas = 0
        self._tiempo_restante_segundos = max(0, int(duracion_segundos))
        self._al_finalizar_examen = al_finalizar

        barra_estado = tk.Frame(self.contenedor, bg="#edf2f7", padx=12, pady=6)
        barra_estado.pack(fill="x", padx=15, pady=(12, 6))

        tk.Label(
            barra_estado, text="● Monitoreo y cortafuegos activos",
            font=("Segoe UI", 9, "bold"), bg="#edf2f7", fg="#2f855a",
        ).pack(side="left")

        lbl_timer = tk.Label(
            barra_estado,
            text=f"Tiempo: {self._formatear_tiempo(self._tiempo_restante_segundos)}",
            font=("Consolas", 12, "bold"), bg="#edf2f7", fg="#c53030",
        )
        lbl_timer.pack(side="right")

        self._lbl_alertas = tk.Label(
            self.contenedor,
            text="Alertas de entorno registradas: 0",
            font=("Segoe UI", 9), bg="#ffffff", fg="#718096",
        )
        self._lbl_alertas.pack(anchor="w", padx=18, pady=(0, 4))

        txt_instrucciones = tk.Text(
            self.contenedor, height=9, font=("Segoe UI", 9), relief="solid", bd=1
        )
        txt_instrucciones.pack(fill="both", expand=True, padx=15, pady=6)
        txt_instrucciones.insert("1.0", instrucciones)
        txt_instrucciones.configure(state="disabled")

        tk.Button(
            self.contenedor, text="Entregar Examen", bg="#c53030", fg="#ffffff",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=6,
            command=self._confirmar_entrega,
        ).pack(pady=10)

        self._programar_tick(lbl_timer)

    def notificar_alerta_visual(self, termino: str, ventana: str) -> None:
        self._contador_alertas += 1
        if self._lbl_alertas is not None and self._lbl_alertas.winfo_exists():
            self._lbl_alertas.configure(
                text=f"⚠ Alerta registrada ({self._contador_alertas}): {termino} detectado en '{ventana[:35]}'",
                fg="#c53030",
                font=("Segoe UI", 9, "bold"),
            )

    def _programar_tick(self, lbl_timer: tk.Label) -> None:
        if self._tiempo_restante_segundos <= 0:
            self._disparar_finalizacion()
            return
        self._tiempo_restante_segundos -= 1
        lbl_timer.configure(text=f"Tiempo: {self._formatear_tiempo(self._tiempo_restante_segundos)}")
        self._timer_id = self.after(1000, lambda: self._programar_tick(lbl_timer))

    def _disparar_finalizacion(self) -> None:
        if self._entrega_en_curso:
            return
        self._entrega_en_curso = True
        self.examen_activo = False
        self._detener_cronometro()
        if self._al_finalizar_examen:
            self._al_finalizar_examen()

    def _confirmar_entrega(self) -> None:
        if self._entrega_en_curso:
            return
        if messagebox.askyesno("Confirmar entrega", "¿Está seguro de entregar y finalizar el examen?"):
            self._disparar_finalizacion()

    def mostrar_fase_finalizacion(
        self,
        mensaje: str,
        ruta_archivo: Path | None = None,
        completado: bool = True,
        al_cerrar: Callable[[], None] | None = None,
    ) -> None:
        self._limpiar_contenedor()
        color = "#2f855a" if completado else "#c53030"
        tk.Label(
            self.contenedor, text=mensaje, font=("Segoe UI", 10, "bold"),
            bg="#ffffff", fg=color, wraplength=520, justify="left",
        ).pack(pady=(35, 15), padx=20)

        if ruta_archivo is not None and ruta_archivo.exists():
            tk.Button(
                self.contenedor,
                text="Abrir Carpeta de Evidencias",
                bg="#2b6cb0",
                fg="#ffffff",
                font=("Segoe UI", 9, "bold"),
                relief="flat",
                padx=12,
                pady=5,
                command=lambda: os.startfile(str(ruta_archivo.parent)),
            ).pack(pady=6)

        tk.Button(
            self.contenedor, text="Cerrar Aplicación", bg="#4a5568", fg="#ffffff",
            font=("Segoe UI", 10), relief="flat", padx=15, pady=6,
            command=al_cerrar if al_cerrar else self.destroy,
        ).pack(pady=12)

    @staticmethod
    def _formatear_tiempo(total_segundos: int) -> str:
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"