"""Nó: infraestrutura (sockets, envio com atraso, timers, laço principal e despacho).

Cada nó é um PROCESSO do sistema operacional com seu próprio socket UDP em
127.0.0.1:(5000 + id). A TOPOLOGIA é imposta pelos próprios nós, como o alcance
de um rádio:

  * um nó só ENVIA para vizinhos (send_hop recusa qualquer outro destino);
  * um nó só ACEITA pacotes de vizinhos: a origem é identificada pela porta UDP
    de origem (não pelo conteúdo da mensagem) e o resto é descartado e logado.

A lógica do protocolo fica nos componentes: Election, Router, Resources, Control.
"""

import heapq
import itertools
import json
import os
import select
import socket
import time

import messages as m
from config import BASE_PORT, CAPACITY, DEFAULT_STEP_DELAY, HOST, N, Timing
from logger import NodeLog
from node.control import Control
from node.election import Election
from node.resources import Resources
from node.routing import Router


class Node:
    def __init__(self, node_id, neighbors, step_delay):
        self.id = node_id
        self.neighbors = set(neighbors)
        self.capacity = CAPACITY[node_id]
        self.t = Timing(step_delay)
        self.log = NodeLog(node_id)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((HOST, BASE_PORT + node_id))

        self.outbox = []   # (instante, n, destino, bytes): envio com atraso por salto
        self.timers = []   # (instante, n, tipo, argumentos)
        self.seq = itertools.count()

        self.leader = None  # compartilhado: a eleição escreve, os recursos leem

        self.election = Election(self)
        self.router = Router(self)
        self.resources = Resources(self)
        self.control = Control(self)

        # mensagens de vizinhos: tipo -> handler(sender, msg)
        self.handlers = {
            m.PROBE: self.election.on_probe,
            m.ECHO: self.election.on_echo,
            m.REJECT: self.election.on_reject,
            m.ANNOUNCE: self.election.on_announce,
        }
        for kind in m.ROUTED_TYPES:
            self.handlers[kind] = self.router.on_hop

        # timers: tipo -> handler(*args)
        self.timer_handlers = {
            "wave_timeout": self.election.on_wave_timeout,
            "wave_expire": self.election.on_wave_expire,
            "req_timeout": self.resources.on_req_timeout,
            "grace_end": self.resources.on_grace_end,
        }

    # ------------------------------------------------------------- infraestrutura
    def send_hop(self, dest, msg):
        """Único ponto de saída de pacotes do protocolo: só vizinhos."""
        if dest not in self.neighbors:
            self.log.error(f"BUG: {msg['type']} para sta{dest}, que não é vizinho. Bloqueado.")
            return
        due = time.monotonic() + self.t.step_delay
        heapq.heappush(self.outbox, (due, next(self.seq), dest, json.dumps(msg).encode()))

    def after(self, seconds, kind, *args):
        heapq.heappush(self.timers, (time.monotonic() + seconds, next(self.seq), kind, args))

    # ------------------------------------------------------------------ despacho
    def dispatch(self, msg, addr):
        kind = msg.get("type")
        if not isinstance(kind, str):
            return
        sender = addr[1] - BASE_PORT  # identidade vem da porta de origem, não do conteúdo
        from_node = addr[0] == HOST and 1 <= sender <= N
        if kind.startswith(m.CTRL_PREFIX):
            if not from_node:
                self.control.on_control(msg, addr)
            return
        if not from_node:
            return
        if sender not in self.neighbors:
            self.log.error(f"🚫 DESCARTADO {kind} vindo de sta{sender}: não é vizinho (fora de alcance).")
            return
        handler = self.handlers.get(kind)
        if handler is None:
            return
        try:
            handler(sender, msg)
        except (KeyError, TypeError, ValueError):
            self.log.error(f"⚠️ {kind} malformado de sta{sender}; descartado.")

    # ------------------------------------------------------------- laço principal
    def run(self):
        self.log.ok(f"🟢 Processo ativo (pid SO {os.getpid()}) em {HOST}:{BASE_PORT + self.id} | "
                    f"vizinhos: {sorted(self.neighbors)} | capacidade {self.capacity}")
        while True:
            now = time.monotonic()
            while self.outbox and self.outbox[0][0] <= now:
                _, _, dest, data = heapq.heappop(self.outbox)
                try:
                    self.sock.sendto(data, (HOST, BASE_PORT + dest))
                except OSError:
                    pass
            while self.timers and self.timers[0][0] <= now:
                _, _, kind, args = heapq.heappop(self.timers)
                self.timer_handlers[kind](*args)

            nxt = min([q[0][0] for q in (self.outbox, self.timers) if q] + [now + 0.2])
            ready, _, _ = select.select([self.sock], [], [], max(0.0, min(nxt - time.monotonic(), 0.2)))
            if not ready:
                continue
            try:
                data, addr = self.sock.recvfrom(4096)
                msg = json.loads(data.decode())
            except (OSError, ValueError):
                continue
            if isinstance(msg, dict):
                self.dispatch(msg, addr)


def run_node_process(node_id, neighbors, step_delay=DEFAULT_STEP_DELAY):
    """Alvo do multiprocessing (spawn): precisa estar no nível do módulo para ser importável."""
    Node(node_id, neighbors, step_delay).run()
