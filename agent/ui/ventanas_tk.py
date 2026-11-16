"""Interfaz gráfica ligera orientada a fases con Tkinter."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Callable


class InterfazFases(tk.Tk):
    """Ventana principal que gestiona la transición entre fases del examen."""

    def __init__(self, mac_estacion: str = "") -> None:
        super().__init__()
        self.mac_estacion = mac_estacion
        self.title("EVIDENS - Cliente de Examen")
        self.geometry("640x500")
        self.minsize(580, 440)
        self.configure(bg="#f4f6f9")

        self._tiempo_restante_segundos = 0
        self._timer_id: str | None = None
        self._al_finalizar_examen: Callable[[], None] | None = None
        self._entrega_en_curso = False  # guard anti doble-disparo

        self._construir_encabezado()
        self.contenedor = tk.Frame(self, bg="#ffffff", bd=1, relief="solid")
        self.contenedor.pack(fill="both", expand=True, padx=20, pady=15)

    def _construir_encabezado(self) -> None:
        encabezado = tk.Frame(self, bg="#1a365d", height=50)
        encabezado.pack(fill="x", side="top")
        tk.Label(
            encabezado, text="EVIDENS", fg="#ffffff", bg="#1a365d",
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left", padx=15, pady=8)
        tk.Label(
            encabezado,
            text=f"Estación: {self.mac_estacion or 'Sin MAC'}",
            fg="#cbd5e1", bg="#1a365d", font=("Segoe UI", 9),
        ).pack(side="right", padx=15, pady=10)

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
        for widget in self.contenedor.winfo_children():
            widget.destroy()

    def mostrar_fase_token(self, al_validar: Callable[[str], None]) -> None:
        """Fase 1: Entrada del token del estudiante."""
        self._limpiar_contenedor()
        tk.Label(
            self.contenedor, text="Ingrese el Token de Sesión",
            font=("Segoe UI", 13, "bold"), bg="#ffffff", fg="#2d3748",
        ).pack(pady=(40, 10))
        tk.Label(
            self.contenedor,
            text="El docente proporcionará el código asignado a su estación.",
            font=("Segoe UI", 10), bg="#ffffff", fg="#718096",
        ).pack(pady=(0, 20))

        entrada_token = ttk.Entry(self.contenedor, font=("Consolas", 16), justify="center")
        entrada_token.pack(pady=10, ipady=6, ipadx=10)
        entrada_token.focus()

        def _enviar() -> None:
            token = entrada_token.get().strip()
            if not token:
                messagebox.showwarning("Atención", "Por favor ingrese un token.")
                return
            al_validar(token)

        tk.Button(
            self.contenedor, text="Validar y Continuar", bg="#2b6cb0", fg="#ffffff",
            font=("Segoe UI", 11, "bold"), relief="flat", padx=15, pady=8,
            command=_enviar,
        ).pack(pady=25)

    def mostrar_fase_vlsm(
        self, datos_vlsm: dict[str, Any], al_reintentar_check: Callable[[], None]
    ) -> None:
        """Fase 2: Presentación de requerimientos VLSM y espera de aprobación docente."""
        self._limpiar_contenedor()
        tk.Label(
            self.contenedor, text="Requerimientos de Subneteo (VLSM)",
            font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#2d3748",
        ).pack(pady=(15, 5))

        txt_info = tk.Text(self.contenedor, height=10, font=("Consolas", 9), relief="solid", bd=1)
        txt_info.pack(fill="both", expand=True, padx=20, pady=10)
        txt_info.insert("1.0", str(datos_vlsm.get("detalles", "Sin requerimientos asignados")))
        txt_info.configure(state="disabled")

        tk.Label(
            self.contenedor,
            text="Esperando validación manual del docente desde el panel web...",
            font=("Segoe UI", 10, "italic"), bg="#ffffff", fg="#d69e2e",
        ).pack(pady=5)

        tk.Button(
            self.contenedor, text="Comprobar Estado de Habilitación",
            bg="#4a5568", fg="#ffffff", font=("Segoe UI", 10),
            relief="flat", padx=10, pady=5, command=al_reintentar_check,
        ).pack(pady=10)

    def mostrar_fase_examen(
        self, duracion_segundos: int, instrucciones: str, al_finalizar: Callable[[], None]
    ) -> None:
        """Fase 3: Examen activo con cronómetro local y monitoreo."""
        self._limpiar_contenedor()
        self._tiempo_restante_segundos = max(0, int(duracion_segundos))
        self._al_finalizar_examen = al_finalizar

        lbl_timer = tk.Label(
            self.contenedor, text=self._formatear_tiempo(self._tiempo_restante_segundos),
            font=("Segoe UI", 26, "bold"), bg="#ffffff", fg="#c53030",
        )
        lbl_timer.pack(pady=(15, 5))

        tk.Label(
            self.contenedor, text="● Monitoreo de actividad y cortafuegos activos",
            font=("Segoe UI", 9, "bold"), bg="#ffffff", fg="#2f855a",
        ).pack(pady=(0, 10))

        txt_instrucciones = tk.Text(
            self.contenedor, height=8, font=("Segoe UI", 9), relief="solid", bd=1
        )
        txt_instrucciones.pack(fill="both", expand=True, padx=20, pady=10)
        txt_instrucciones.insert("1.0", instrucciones)
        txt_instrucciones.configure(state="disabled")

        tk.Button(
            self.contenedor, text="Entregar Examen", bg="#c53030", fg="#ffffff",
            font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=6,
            command=self._confirmar_entrega,
        ).pack(pady=10)

        self._programar_tick(lbl_timer)

    def _programar_tick(self, lbl_timer: tk.Label) -> None:
        """Programa el próximo tick. Si ya llegó a 0, dispara la finalización."""
        if self._tiempo_restante_segundos <= 0:
            self._disparar_finalizacion()
            return
        self._tiempo_restante_segundos -= 1
        lbl_timer.configure(text=self._formatear_tiempo(self._tiempo_restante_segundos))
        self._timer_id = self.after(1000, lambda: self._programar_tick(lbl_timer))

    def _disparar_finalizacion(self) -> None:
        """Guarda contra doble disparo (doble clic o cronómetro + clic)."""
        if self._entrega_en_curso:
            return
        self._entrega_en_curso = True
        self._detener_cronometro()
        if self._al_finalizar_examen:
            self._al_finalizar_examen()

    def _confirmar_entrega(self) -> None:
        if self._entrega_en_curso:
            return
        if messagebox.askyesno("Confirmar", "¿Está seguro de entregar el examen anticipadamente?"):
            self._disparar_finalizacion()

    def mostrar_fase_finalizacion(
        self,
        mensaje: str,
        completado: bool = True,
        al_cerrar: Callable[[], None] | None = None,
    ) -> None:
        """Fase 4: Empaquetado y entrega final de evidencias.

        Si `al_cerrar` se proporciona, el botón "Cerrar Aplicación" lo invoca;
        si no, se cierra directamente la ventana. Recomendado pasar el manejador
        del orquestador para garantizar la restauración del archivo hosts.
        """
        self._limpiar_contenedor()
        color = "#2f855a" if completado else "#c53030"
        tk.Label(
            self.contenedor, text=mensaje, font=("Segoe UI", 12, "bold"),
            bg="#ffffff", fg=color, wraplength=480,
        ).pack(pady=(60, 20))

        def _cerrar() -> None:
            if al_cerrar is not None:
                al_cerrar()
            else:
                self.destroy()

        tk.Button(
            self.contenedor, text="Cerrar Aplicación", bg="#4a5568", fg="#ffffff",
            font=("Segoe UI", 10), padx=15, pady=6, command=_cerrar,
        ).pack(pady=20)

    @staticmethod
    def _formatear_tiempo(total_segundos: int) -> str:
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        return f"{horas:02d}:{minutos:02d}:{segundos:02d}"