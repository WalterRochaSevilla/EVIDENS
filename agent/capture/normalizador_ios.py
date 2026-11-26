"""Normalización de comandos Cisco IOS (Redes I) y simulación de edición CLI (↑/↓/←/→ y ?)."""

import re

_REGLAS_IOS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Básicos y seguridad
    (re.compile(r"^en(?:a(?:b(?:le?)?)?)?$", re.I), "enable"),
    (re.compile(r"^conf(?:ig(?:ure)?)?\s+t(?:erm(?:inal)?)?$", re.I), "configure terminal"),
    (re.compile(r"^hos(?:t(?:name)?)?\s+(.+)$", re.I), r"hostname \1"),
    (re.compile(r"^ban(?:n(?:er)?)?\s+m(?:o(?:td)?)?\s+(.+)$", re.I), r"banner motd \1"),
    (re.compile(r"^en(?:a(?:ble)?)?\s+pass(?:w(?:ord)?)?\s+(.+)$", re.I), r"enable password \1"),
    (re.compile(r"^en(?:a(?:ble)?)?\s+sec(?:r(?:et)?)?\s+(.+)$", re.I), r"enable secret \1"),
    (re.compile(r"^line?\s+con(?:s(?:ole)?)?\s+(\d+)$", re.I), r"line console \1"),
    (re.compile(r"^pass(?:w(?:ord)?)?\s+(.+)$", re.I), r"password \1"),
    (re.compile(r"^serv(?:i(?:ce)?)?\s+pass(?:w(?:ord)?)?(?:-encrypt(?:ion)?)?$", re.I), "service password-encryption"),
    (re.compile(r"^cop(?:y)?\s+r(?:u(?:n(?:ning-config)?)?)?\s+s(?:t(?:a(?:rt(?:up-config)?)?)?)?$", re.I), "copy running-config startup-config"),
    (re.compile(r"^wr(?:i(?:te)?)?$", re.I), "write memory"),
    (re.compile(r"^do\s+wr(?:i(?:te)?)?$", re.I), "do write memory"),
    (re.compile(r"^ex(?:i(?:t)?)?$", re.I), "exit"),
    # Interfaces, subinterfaces, EtherChannel e IP
    (re.compile(r"^int(?:er(?:face)?)?\s+ran(?:g(?:e)?)?\s+(.+)$", re.I), r"interface range \1"),
    (re.compile(r"^int(?:er(?:face)?)?\s+po(?:rt(?:-channel)?)?\s+(\d+)$", re.I), r"interface port-channel \1"),
    (re.compile(r"^int(?:er(?:face)?)?\s+(.+)$", re.I), r"interface \1"),
    (re.compile(r"^ip\s+ad(?:d(?:r(?:ess)?)?)?\s+(.+)$", re.I), r"ip address \1"),
    (re.compile(r"^sh(?:u(?:t(?:down)?)?)?$", re.I), "shutdown"),
    # DHCP
    (re.compile(r"^ip\s+dhcp\s+exc(?:l(?:u(?:d(?:ed(?:-address)?)?)?)?)?\s+(.+)$", re.I), r"ip dhcp excluded-address \1"),
    (re.compile(r"^def(?:a(?:u(?:lt(?:-router)?)?)?)?\s+(.+)$", re.I), r"default-router \1"),
    (re.compile(r"^dns(?:-s(?:e(?:r(?:v(?:er)?)?)?)?)?\s+(.+)$", re.I), r"dns-server \1"),
    # Enrutamiento estático y dinámico (RIP v2)
    (re.compile(r"^ip\s+ro(?:u(?:t(?:e)?)?)?\s+(.+)$", re.I), r"ip route \1"),
    (re.compile(r"^rou(?:t(?:er)?)?\s+rip$", re.I), "router rip"),
    (re.compile(r"^ver(?:s(?:i(?:o(?:n)?)?)?)?\s+(\d+)$", re.I), r"version \1"),
    (re.compile(r"^au(?:t(?:o(?:-summary)?)?)?$", re.I), "auto-summary"),
    (re.compile(r"^net(?:w(?:ork)?)?\s+(.+)$", re.I), r"network \1"),
    # VLANs, Switchport, VTP y EtherChannel
    (re.compile(r"^enc(?:a(?:p(?:s(?:u(?:l(?:a(?:t(?:ion)?)?)?)?)?)?)?)?\s+dot1q\s+(.+)$", re.I), r"encapsulation dot1q \1"),
    (re.compile(r"^sw(?:i(?:t(?:c(?:h(?:p(?:o(?:r(?:t)?)?)?)?)?)?)?)?\s+mo(?:d(?:e)?)?\s+tr(?:u(?:n(?:k)?)?)?$", re.I), "switchport mode trunk"),
    (re.compile(r"^sw(?:i(?:t(?:c(?:h(?:p(?:o(?:r(?:t)?)?)?)?)?)?)?)?\s+mo(?:d(?:e)?)?\s+acc(?:e(?:s(?:s)?)?)?$", re.I), "switchport mode access"),
    (re.compile(r"^sw(?:i(?:t(?:c(?:h(?:p(?:o(?:r(?:t)?)?)?)?)?)?)?)?\s+acc(?:e(?:s(?:s)?)?)?\s+vlan\s+(\d+)$", re.I), r"switchport access vlan \1"),
    (re.compile(r"^vtp\s+mo(?:d(?:e)?)?\s+ser(?:v(?:e(?:r)?)?)?$", re.I), "vtp mode server"),
    (re.compile(r"^vtp\s+mo(?:d(?:e)?)?\s+cli(?:e(?:n(?:t)?)?)?$", re.I), "vtp mode client"),
    (re.compile(r"^vtp\s+mo(?:d(?:e)?)?\s+trans(?:p(?:a(?:r(?:e(?:n(?:t)?)?)?)?)?)?$", re.I), "vtp mode transparent"),
    (re.compile(r"^vtp\s+dom(?:a(?:i(?:n)?)?)?\s+(.+)$", re.I), r"vtp domain \1"),
    (re.compile(r"^vtp\s+pass(?:w(?:o(?:r(?:d)?)?)?)?\s+(.+)$", re.I), r"vtp password \1"),
    (re.compile(r"^ch(?:a(?:n(?:n(?:e(?:l(?:-g(?:r(?:o(?:u(?:p)?)?)?)?)?)?)?)?)?)?\s+(\d+)\s+mo(?:d(?:e)?)?\s+(des(?:irable)?|act(?:ive)?|au(?:to)?|pas(?:sive)?|on)$", re.I), r"channel-group \1 mode \2"),
    # Consultas show
    (re.compile(r"^sh(?:o(?:w)?)?\s+run(?:ning-config)?$", re.I), "show running-config"),
    (re.compile(r"^sh(?:o(?:w)?)?\s+ip\s+int(?:erface)?\s+br(?:ief)?$", re.I), "show ip interface brief"),
    (re.compile(r"^sh(?:o(?:w)?)?\s+vl(?:a(?:n)?)?(?:\s+br(?:ief)?)?$", re.I), "show vlan brief"),
)

_MODOS_ETHERCHANNEL = {"des": "desirable", "act": "active", "au": "auto", "pas": "passive"}


def _normalizar_base(texto: str) -> str:
    for patron, reemplazo in _REGLAS_IOS:
        if patron.match(texto):
            res = patron.sub(reemplazo, texto)
            if res.startswith("channel-group "):
                partes = res.split()
                partes[-1] = _MODOS_ETHERCHANNEL.get(partes[-1].lower(), partes[-1].lower())
                return " ".join(partes)
            return res
    return texto


def normalizar_comando_ios(comando: str) -> str:
    """Expande abreviaturas Cisco IOS (incluyendo comandos negados con prefijo 'no ')."""
    texto = re.sub(r"\s+", " ", (comando or "").strip())
    if texto.lower().startswith("no "):
        interno = texto[3:].strip()
        return f"no {_normalizar_base(interno)}"
    return _normalizar_base(texto)


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
