"""Logs: NodeLog (lado do nó, formata e envia) e logger_listener (processo principal, imprime)."""

import json
import socket
import time

from colors import C_BOLD, C_CYAN, C_GREEN, C_MAGENTA, C_RED, C_RESET, C_YELLOW
from config import HOST, LOGGER_PORT


class NodeLog:
    """Log de um nó. Cada método corresponde a uma cor; a lógica do nó não conhece códigos ANSI."""

    def __init__(self, node_id):
        self.node_id = node_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def _emit(self, color, text, bold):
        text = f"{color}{C_BOLD if bold else ''}{text}{C_RESET}"
        try:
            self.sock.sendto(json.dumps({"node": self.node_id, "text": text}).encode(), (HOST, LOGGER_PORT))
        except OSError:
            pass

    def info(self, text, bold=False):     # ciclo de eleição, roteamento
        self._emit(C_CYAN, text, bold)

    def ok(self, text, bold=False):       # sucesso
        self._emit(C_GREEN, text, bold)

    def warn(self, text, bold=False):     # atenção / espera
        self._emit(C_YELLOW, text, bold)

    def error(self, text, bold=False):    # rejeição / falha
        self._emit(C_RED, text, bold)

    def request(self, text, bold=False):  # pedidos de recurso
        self._emit(C_MAGENTA, text, bold)


def logger_listener():
    """Roda numa thread do processo principal: recebe os logs dos nós e imprime no terminal."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, LOGGER_PORT))
    while True:
        try:
            data, _ = sock.recvfrom(4096)
            payload = json.loads(data.decode())
            t_str = time.strftime("%H:%M:%S")
            print(f"\r[{t_str}] [sta{payload['node']:2d}] {payload['text']}\n> ", end="", flush=True)
        except Exception:
            continue
