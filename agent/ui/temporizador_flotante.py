"""Widget flotante de temporizador en esquina y modal de control docente."""

import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog
from typing import Any, Callable

from core.configuracion import verificar_pin_docente


class TemporizadorFlotante(tk.Toplevel):
    """Ventana compacta sin bordes (always-on-top) ubicada en la esquina superior derecha."""

    def __init__(
        self,
        master: tk.Tk,
        carpeta_trabajo: Path,
        al_restaurar: Callable[[], None],
        al_atajo_docente: Callable[[], None],
    ) -> None:
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#38bdf8", padx=1, pady=1)

        self._carpeta_trabajo = carpeta_trabajo
        self._al_restaurar = al_restaurar
        self._al_atajo_docente = al_atajo_docente
        self._drag_x, self._drag_y = 0, 0

        ancho, alto = 228, 80
        pos_x = max(10, self.winfo_screenwidth() - ancho - 18)
        self.geometry(f"{ancho}x{alto}+{pos_x}+16")

        cuerpo = tk.Frame(self, bg="#0f172a")
        cuerpo.pack(fill="both", expand=True)

        barra = tk.Frame(cuerpo, bg="#1e3a8a", height=24)
        barra.pack(fill="x", side="top")

        lbl_marca = tk.Label(
            barra, text="🛡 EVIDENS", fg="#ffffff", bg="#1e3a8a", font=("Segoe UI", 8, "bold"), cursor="fleur"
        )
        lbl_marca.pack(side="left", padx=6, pady=2)
        for widget in (lbl_marca, barra):
            widget.bind("<ButtonPress-1>", self._iniciar_arrastre)
            widget.bind("<B1-Motion>", self._mover_ventana)

        tk.Button(
            barra, text="🗖", bg="#1e3a8a", fg="#e2e8f0", font=("Segoe UI", 8, "bold"),
            relief="flat", bd=0, padx=5, command=self._al_restaurar,
        ).pack(side="right", padx=2)
        tk.Button(
            barra, text="📂 .pkt", bg="#2563eb", fg="#ffffff", font=("Segoe UI", 7, "bold"),
            relief="flat", bd=0, padx=5, command=self._abrir_trabajo,
        ).pack(side="right", padx=2, pady=2)

        self.lbl_reloj = tk.Label(
            cuerpo, text="01:30:00", fg="#f8fafc", bg="#0f172a", font=("Consolas", 16, "bold")
        )
        self.lbl_reloj.pack(pady=(4, 0))
        self.lbl_reloj.bind("<Double-Button-1>", lambda _e: self._al_restaurar())

        self.lbl_estado = tk.Label(
            cuerpo, text="● Monitoreo activo", fg="#4ade80", bg="#0f172a", font=("Segoe UI", 7, "bold")
        )
        self.lbl_estado.pack(pady=(0, 3))

        self.bind("<KeyPress>", self._detectar_tecla)
        self.bind("<F12>", lambda _e: self._al_atajo_docente())

    def _iniciar_arrastre(self, event: Any) -> None:
        self._drag_x, self._drag_y = event.x, event.y

    def _mover_ventana(self, event: Any) -> None:
        x = self.winfo_x() + (event.x - self._drag_x)
        y = self.winfo_y() + (event.y - self._drag_y)
        self.geometry(f"+{x}+{y}")

    def _abrir_trabajo(self) -> None:
        try:
            os.startfile(str(self._carpeta_trabajo))
        except OSError:
            pass

    def _detectar_tecla(self, event: Any) -> None:
        if (getattr(event, "state", 0) & 0x4) and getattr(event, "keycode", 0) == 68:
            self._al_atajo_docente()

    def actualizar_reloj(self, texto_tiempo: str, pocos_minutos: bool = False) -> None:
        if self.winfo_exists():
            self.lbl_reloj.configure(text=texto_tiempo, fg="#f87171" if pocos_minutos else "#f8fafc")
            self.attributes("-topmost", True)

    def actualizar_metricas(self, alertas: int, clips: int) -> None:
        if not self.winfo_exists():
            return
        if alertas > 0:
            self.lbl_estado.configure(text=f"⚠ Alertas: {alertas} | Clips: {clips}", fg="#fbbf24")
        else:
            self.lbl_estado.configure(text="● Monitoreo activo", fg="#4ade80")


def abrir_dialogo_control_docente(
    raiz: tk.Tk,
    padre_dialogo: tk.Misc,
    en_espera_vlsm: bool,
    examen_activo: bool,
    al_habilitar: Callable[[], None] | None,
    al_forzar_salida: Callable[[], None] | None,
    al_ajustar_tiempo: Callable[[int], None],
    al_disparar_fin: Callable[[str], None],
) -> None:
    """Solicita PIN docente (SHA-256) y abre el modal de control sobre cualquier ventana."""
    pin = simpledialog.askstring("Autorización Docente", "Ingrese la clave de control docente:", show="*", parent=padre_dialogo)
    if not verificar_pin_docente(pin):
        if pin is not None:
            messagebox.showerror("Acceso denegado", "Clave docente incorrecta.", parent=padre_dialogo)
        return

    modal = tk.Toplevel(raiz)
    modal.title("Panel de Control Docente")
    modal.geometry("360x240")
    modal.configure(bg="#ffffff")
    modal.attributes("-topmost", True)
    modal.grab_set()
    tk.Label(modal, text="Control Docente de Estación", font=("Segoe UI", 11, "bold"), bg="#ffffff", fg="#1a365d").pack(pady=(14, 10))

    if en_espera_vlsm and al_habilitar:
        tk.Button(modal, text="✔ Habilitar Estación e Iniciar Examen", bg="#2f855a", fg="#ffffff", font=("Segoe UI", 9, "bold"), width=34, pady=6, command=lambda: [modal.destroy(), al_habilitar()]).pack(pady=8)
        tk.Button(modal, text="✖ Cancelar y Cerrar Aplicación", bg="#c53030", fg="#ffffff", font=("Segoe UI", 9, "bold"), width=34, pady=6, command=lambda: [modal.destroy(), al_forzar_salida() if al_forzar_salida else raiz.destroy()]).pack(pady=6)
    elif examen_activo:
        fila = tk.Frame(modal, bg="#ffffff")
        fila.pack(pady=4)
        tk.Button(fila, text="+5 Minutos", bg="#2b6cb0", fg="#ffffff", font=("Segoe UI", 9, "bold"), padx=12, pady=4, command=lambda: al_ajustar_tiempo(300)).pack(side="left", padx=6)
        tk.Button(fila, text="-5 Minutos", bg="#d69e2e", fg="#ffffff", font=("Segoe UI", 9, "bold"), padx=12, pady=4, command=lambda: al_ajustar_tiempo(-300)).pack(side="left", padx=6)
        tk.Button(modal, text="✔ Marcar Examen Finalizado (Entregar)", bg="#2f855a", fg="#ffffff", font=("Segoe UI", 9, "bold"), width=34, pady=5, command=lambda: [modal.destroy(), al_disparar_fin("FINALIZADO_POR_DOCENTE")]).pack(pady=(12, 4))
        tk.Button(modal, text="✖ Anular / Cortar Ejecución", bg="#c53030", fg="#ffffff", font=("Segoe UI", 9, "bold"), width=34, pady=5, command=lambda: [modal.destroy(), al_disparar_fin("ANULADO_POR_DOCENTE")]).pack(pady=4)
