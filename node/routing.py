"""Roteamento salto a salto pela árvore criada pela eleição.

Cada ECHO informa os membros da subárvore do remetente, então cada nó sabe por
qual filho chegar a um destino (ou sobe ao pai).
"""

from config import N


class Router:
    def __init__(self, node):
        self.node = node
        self.log = node.log

    def next_hop(self, dest):
        election = self.node.election
        for child, members in election.children.items():
            if dest in members:
                return child
        return election.parent

    def send_routed(self, dest, payload):
        self.route(dict(payload, src=self.node.id, dest=dest, ttl=N))

    def on_hop(self, sender, msg):
        """Handler de pacote roteado recebido de um vizinho."""
        self.route(msg)

    def route(self, msg):
        n = self.node
        if msg["dest"] == n.id:
            n.resources.on_routed(msg)
            return
        if msg["ttl"] <= 0:
            self.log.error(f"⚠️ {msg['type']} de sta{msg['src']} para sta{msg['dest']} descartado (TTL).")
            return
        hop = self.next_hop(msg["dest"])
        if hop is None:
            self.log.error(f"⚠️ Sem rota para sta{msg['dest']}: {msg['type']} de sta{msg['src']} descartado.")
            return
        if msg["src"] != n.id:
            self.log.info(f"↪ Encaminhando {msg['type']} sta{msg['src']} → sta{msg['dest']} via sta{hop}")
        n.send_hop(hop, dict(msg, ttl=msg["ttl"] - 1))
