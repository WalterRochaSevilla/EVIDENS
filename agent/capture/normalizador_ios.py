"""Normalización de abreviaturas Cisco IOS y simulación de edición CLI (flechas ↑/↓/←/→ y ?)."""

import re

_REGLAS_IOS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^en(?:a(?:b(?:le?)?)?)?$", re.I), "enable"),
    (re.compile(r"^conf(?:ig(?:ure)?)?\s+t(?:erm(?:inal)?)?$", re.I), "configure terminal"),
    (re.compile(r"^hos(?:t(?:name)?)?\s+(.+)$", re.I), r"hostname \1"),
    (re.compile(r"^int(?:er(?:face)?)?\s+(.+)$", re.I), r"interface \1"),
    (re.compile(r"^ip\s+ad(?:d(?:r(?:ess)?)?)?\s+(.+)$", re.I), r"ip address \1"),
    (re.compile(r"^no\s+sh(?:u(?:t(?:down)?)?)?$", re.I), "no shutdown"),
    (re.compile(r"^sh(?:u(?:t(?:down)?)?)?$", re.I), "shutdown"),
    (re.compile(r"^no\s+au(?:t(?:o(?:-summary)?)?)?$", re.I), "no auto-summary"),
    (re.compile(r"^net(?:w(?:ork)?)?\s+(.+)$", re.I), r"network \1"),
    (re.compile(r"^sh(?:o(?:w)?)?\s+run(?:ning-config)?$", re.I), "show running-config"),
    (re.compile(r"^sh(?:o(?:w)?)?\s+ip\s+int(?:erface)?\s+br(?:ief)?$", re.I), "show ip interface brief"),
    (re.compile(r"^wr(?:i(?:te)?)?$", re.I), "write memory"),
    (re.compile(r"^do\s+wr(?:i(?:te)?)?$", re.I), "do write memory"),
    (re.compile(r"^ex(?:i(?:t)?)?$", re.I), "exit"),
)


def normalizar_comando_ios(comando: str) -> str:
    """Expande abreviaturas comunes de Cisco IOS conservando argumentos e IPs."""
    texto = re.sub(r"\s+", " ", (comando or "").strip())
    for patron, reemplazo in _REGLAS_IOS:
        if patron.match(texto):
            return patron.sub(reemplazo, texto)
    return texto


class EditorLineaCLI:
    """Simula el búfer de edición y el historial de flechas ↑/↓ de una consola Cisco IOS."""

    def __init__(self) -> None:
        self.chars: list[str] = []
        self.cursor: int = 0
        self.historial: list[str] = []
        self.idx_hist: int | None = None
        self.desde_historial: bool = False

    def _cargar_historial(self, indice: int) -> None:
        self.idx_hist = indice
        self.chars = list(self.historial[indice])
        self.cursor = len(self.chars)
        self.desde_historial = True

    def _reiniciar_linea(self) -> None:
        self.chars, self.cursor, self.idx_hist, self.desde_historial = [], 0, None, False

    def procesar_tecla(self, tecla: str) -> tuple[str, str] | None:
        if tecla == "[enter]":
            texto = "".join(self.chars).strip()
            origen = "historial_flechas" if self.desde_historial else "teclado"
            if texto:
                self.historial.append(texto)
            self._reiniciar_linea()
            return (origen, texto) if texto else None
        if tecla == "?":
            previo = "".join(self.chars).strip()
            return ("ayuda_ios", f"{previo} ?".strip())
        if tecla == "[backspace]" and self.cursor > 0:
            self.chars.pop(self.cursor - 1)
            self.cursor -= 1
        elif tecla == "[delete]" and self.cursor < len(self.chars):
            self.chars.pop(self.cursor)
        elif tecla == "[left]":
            self.cursor = max(0, self.cursor - 1)
        elif tecla == "[right]":
            self.cursor = min(len(self.chars), self.cursor + 1)
        elif tecla == "[home]":
            self.cursor = 0
        elif tecla == "[end]":
            self.cursor = len(self.chars)
        elif tecla == "[up]" and self.historial:
            nuevo_idx = len(self.historial) - 1 if self.idx_hist is None else max(0, self.idx_hist - 1)
            self._cargar_historial(nuevo_idx)
        elif tecla == "[down]" and self.idx_hist is not None:
            if self.idx_hist + 1 < len(self.historial):
                self._cargar_historial(self.idx_hist + 1)
            else:
                self._reiniciar_linea()
        elif tecla in ("[space]", "[tab]"):
            if tecla == "[space]" or (self.cursor > 0 and self.chars[self.cursor - 1] != " "):
                self.chars.insert(self.cursor, " ")
                self.cursor += 1
        elif tecla and not tecla.startswith("["):
            self.chars.insert(self.cursor, tecla)
            self.cursor += 1
        return None
