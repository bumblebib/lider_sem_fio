"""Exclusão mútua centralizada: lado cliente e lado líder.

Os pedidos (REQ/REL/REGISTER_HELD) vão ao líder e as respostas (GRANT/WAIT)
voltam ao solicitante, tudo roteado pela árvore (ver routing.py).
"""

import time

import messages as m
from messages import make_msg


class Resources:
    def __init__(self, node):
        self.node = node
        self.log = node.log

        # lado cliente
        self.pending_req = set()    # pedidos ainda sem resposta do líder
        self.waiting_req = set()    # pedidos confirmados, na fila do líder
        self.held = set()
        self.req_token = {}

        # lado líder
        self.locks = {}
        self.queues = {}
        self.grace_until = 0.0
        self.deferred = []          # (solicitante, recurso) recebidos na janela de re-registro

        self._routed_handlers = {
            m.REQ_RESOURCE: self._on_req,
            m.REL_RESOURCE: self._on_rel,
            m.REGISTER_HELD: self._on_register_held,
            m.GRANT_RESOURCE: self._on_grant,
            m.WAIT_RESOURCE: self._on_wait,
        }

    def has_requests(self):
        return bool(self.pending_req or self.waiting_req)

    # ------------------------------------------------- novo líder anunciado
    def on_leader_known(self, prior):
        """Chamado pela eleição quando o líder é conhecido: (re)registra recursos e reenvia pedidos."""
        n = self.node
        if n.leader == n.id:
            self.locks.clear()
            self.queues.clear()
            self.deferred.clear()
            if prior:
                self.grace_until = time.monotonic() + n.t.register_window
                n.after(n.t.register_window, "grace_end")
                self.log.ok(f"👑 LÍDER: aguardando {n.t.register_window:.1f}s o re-registro dos "
                            f"recursos em uso antes de conceder novos.")
            else:
                self.grace_until = 0.0
        for res in sorted(self.held):
            n.router.send_routed(n.leader, make_msg(m.REGISTER_HELD, resource=res))
        todo = self.pending_req | self.waiting_req
        self.waiting_req.clear()
        self.pending_req = set(todo)
        for res in sorted(todo):
            self.log.request(f"🔑 Re-enviando requisição de '{res}' ao novo líder sta{n.leader}...")
            self.send_request(res)

    # ------------------------------------------------------------- cliente
    def request_resource(self, res):
        n = self.node
        if res in self.held:
            self.log.warn(f"⚠️ Nó já possui o recurso '{res}'.")
            return
        self.waiting_req.discard(res)
        self.pending_req.add(res)
        if n.election.in_election:
            self.log.warn(f"⚠️ SOLICITAÇÃO [{res}]: eleição em andamento, pedido em espera.")
        elif n.leader is None:
            self.log.warn(f"⚠️ SOLICITAÇÃO [{res}]: Sem líder ativo! Pedido em espera. Disparando eleição...")
            n.election.start_election(f"pedido de '{res}' sem líder")
        else:
            self.send_request(res)

    def send_request(self, res):
        n = self.node
        token = self.req_token.get(res, 0) + 1
        self.req_token[res] = token
        self.log.request(f"🔑 Solicitando recurso '{res}' ao líder sta{n.leader}...")
        n.router.send_routed(n.leader, make_msg(m.REQ_RESOURCE, resource=res))
        n.after(n.t.request_timeout, "req_timeout", res, n.leader, token)

    def release_resource(self, res):
        n = self.node
        if res not in self.held:
            self.log.error(f"⚠️ Nó não possui o recurso '{res}' para liberar.")
            return
        self.held.discard(res)
        self.log.warn(f"🔓 Liberando recurso '{res}'... Notificando líder sta{n.leader}")
        if n.leader is not None:
            n.router.send_routed(n.leader, make_msg(m.REL_RESOURCE, resource=res))

    # -------------------------------------------------- pacotes roteados
    def on_routed(self, msg):
        """Pacote cujo destino final é este nó."""
        n = self.node
        kind = msg["type"]
        if kind in m.LEADER_ONLY and n.leader != n.id:
            self.log.error(f"⚠️ {kind} de sta{msg['src']} recebido, mas não sou o líder. Descartado.")
            return
        handler = self._routed_handlers.get(kind)
        if handler:
            handler(msg["src"], msg.get("resource"), msg)

    def _on_req(self, src, res, msg):
        if time.monotonic() < self.grace_until:
            self.deferred.append((src, res))
            self.log.warn(f"👑 LÍDER: pedido de '{res}' por sta{src} adiado até o fim do re-registro.")
            self.node.router.send_routed(src, make_msg(m.WAIT_RESOURCE, resource=res, owner=None))
        else:
            self.leader_request(src, res)

    def _on_rel(self, src, res, msg):
        self.leader_release(src, res)

    def _on_register_held(self, src, res, msg):
        if res in self.locks and self.locks[res] != src:
            self.log.error(f"👑 LÍDER: conflito ao re-registrar '{res}': já em posse de sta{self.locks[res]}.")
        else:
            self.locks[res] = src
            self.log.ok(f"👑 LÍDER: Re-registrou recurso '{res}' em posse de sta{src}")

    def _on_grant(self, src, res, msg):
        self.pending_req.discard(res)
        self.waiting_req.discard(res)
        self.held.add(res)
        self.log.ok(f"🎉 ACESSO CONCEDIDO! Você está usando o recurso '{res}'!", bold=True)

    def _on_wait(self, src, res, msg):
        if res in self.pending_req:
            self.pending_req.discard(res)
            self.waiting_req.add(res)
        owner = msg.get("owner")
        why = f"em uso por sta{owner}" if owner is not None else "líder reconstruindo o estado dos recursos"
        self.log.warn(f"⏳ AGUARDANDO RECURSO '{res}' ({why}). Confirmado na fila pelo líder sta{src}.")

    # ---------------------------------------------------------------- líder
    def leader_request(self, src, res):
        send = self.node.router.send_routed
        owner = self.locks.get(res)
        if owner is None:
            self.locks[res] = src
            self.log.ok(f"👑 LÍDER: Concedeu o recurso '{res}' para sta{src}")
            send(src, make_msg(m.GRANT_RESOURCE, resource=res))
        elif owner == src:
            send(src, make_msg(m.GRANT_RESOURCE, resource=res))
        else:
            queue = self.queues.setdefault(res, [])
            if src not in queue:
                queue.append(src)
                self.log.warn(f"👑 LÍDER: Recurso '{res}' ocupado por sta{owner}. sta{src} colocado na "
                              f"FILA DE ESPERA (Posição: {len(queue)})")
            send(src, make_msg(m.WAIT_RESOURCE, resource=res, owner=owner))

    def leader_release(self, src, res):
        if self.locks.get(res) != src:
            return
        self.log.ok(f"👑 LÍDER: Recurso '{res}' foi liberado por sta{src}")
        queue = self.queues.get(res)
        if queue:
            nxt = queue.pop(0)
            self.locks[res] = nxt
            self.log.ok(f"👑 LÍDER: Concedendo '{res}' para o próximo da fila -> sta{nxt}")
            self.node.router.send_routed(nxt, make_msg(m.GRANT_RESOURCE, resource=res))
        else:
            del self.locks[res]
            self.log.ok(f"👑 LÍDER: Recurso '{res}' agora está LIVRE.")

    # ----------------------------------------------------------------- timers
    def on_req_timeout(self, res, target, token):
        n = self.node
        if (self.req_token.get(res) == token and res in self.pending_req
                and n.leader == target and not n.election.in_election):
            self.log.error(f"⚠️ Líder sta{target} NÃO respondeu ao pedido de '{res}'! "
                           f"Detectada QUEDA do líder. Re-iniciando eleição...")
            n.leader = None
            n.election.start_election(f"líder sta{target} não respondeu")

    def on_grace_end(self):
        if self.node.leader == self.node.id and self.deferred:
            self.log.ok(f"👑 LÍDER: re-registro concluído; atendendo {len(self.deferred)} pedido(s) adiado(s).")
            todo, self.deferred = self.deferred, []
            for src, res in todo:
                self.leader_request(src, res)
