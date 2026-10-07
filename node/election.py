"""Eleição em árvore (convergecast) para redes sem fio, segundo Tanenbaum.

Quem dispara manda PROBE aos vizinhos; o primeiro PROBE recebido define o pai;
PROBEs de outra onda são respondidos com REJECT; as folhas respondem ECHO e cada
nó devolve ao pai o melhor candidato da sua subárvore. Eleições simultâneas são
identificadas por (capacidade, id, época): a de maior chave absorve as outras.
"""

import messages as m
from messages import make_msg


class Election:
    def __init__(self, node):
        self.node = node
        self.log = node.log

        self.epoch = 0
        self.in_election = False
        self.wave = None            # chave (capacidade, id, época) da onda atual
        self.parent = None
        self.children = {}          # filho -> membros da subárvore dele
        self.members = set()
        self.pending = set()        # vizinhos de quem ainda espero ECHO/REJECT
        self.best = (node.capacity, node.id)
        self.prior = False          # alguém na subárvore já teve líder antes?
        self.knew_leader = False
        self.announce_prior = False
        self.closed = set()         # ondas já encerradas (PROBEs atrasados são rejeitados)

    @staticmethod
    def wname(key):
        return f"sta{key[1]}#{key[2]}"

    # ---------------------------------------------------------------- disparo
    def start_election(self, reason):
        n = self.node
        self.epoch += 1
        key = (n.capacity, n.id, self.epoch)
        self.log.info(f"🚀 Iniciando onda de eleição {self.wname(key)} ({reason})", bold=True)
        self.join_wave(key, None, n.t.wave_budget)

    def join_wave(self, key, parent, budget):
        n = self.node
        if self.wave is not None and self.wave != key:
            self.closed.add(self.wave)
        self.in_election = True
        self.wave = key
        self.parent = parent
        self.children = {}
        self.members = {n.id}
        self.best = (n.capacity, n.id)
        self.prior = self.knew_leader
        self.pending = set(n.neighbors) - ({parent} if parent is not None else set())
        n.after(budget, "wave_timeout", key)
        n.after(budget + n.t.announce_grace, "wave_expire", key)

        child_budget = max(budget - n.t.hop_slack, 0.5)
        for nb in sorted(self.pending):
            self.log.info(f"📡 PROBE -> sta{nb} (onda {self.wname(key)})")
            n.send_hop(nb, make_msg(m.PROBE, key=list(key), budget=child_budget))
        if not self.pending:
            self.log.warn("🍃 Nó folha: nenhum vizinho além do pai.")
            self.finish_wave()

    def finish_wave(self):
        """Todos os vizinhos responderam (ou estouraram o prazo)."""
        n = self.node
        key = self.wave
        if self.parent is not None:
            self.log.warn(f"⬆ ECHO -> sta{self.parent} | Melhor da subárvore: "
                          f"sta{self.best[1]} (Cap: {self.best[0]}) | membros: {sorted(self.members)}")
            n.send_hop(self.parent, make_msg(m.ECHO, key=list(key), best=list(self.best),
                                             members=sorted(self.members), prior=self.prior))
            return
        winner = self.best[1]
        self.log.ok(f"🏆 ELEIÇÃO CONCLUÍDA! Vencedor do Convergecast: sta{winner} "
                    f"(Cap: {self.best[0]})", bold=True)
        n.leader = winner
        self.in_election = False
        self.closed.add(key)
        self.announce_prior = self.prior
        self.forward_announce(key, winner, self.prior)
        self.after_announce()

    def forward_announce(self, key, leader, prior):
        for child in sorted(self.children):
            self.node.send_hop(child, make_msg(m.ANNOUNCE, key=list(key), leader=leader, prior=prior))

    def after_announce(self):
        """Depois de saber o líder: o módulo de recursos (re)registra e reenvia pendências."""
        self.knew_leader = True
        self.node.resources.on_leader_known(self.announce_prior)

    # --------------------------------------------------------------- handlers
    def on_probe(self, sender, msg):
        key, budget = tuple(msg["key"]), float(msg["budget"])
        if key in self.closed:
            self.log.error(f"🚫 REJECT -> sta{sender} (onda {self.wname(key)} já encerrada)")
            self.node.send_hop(sender, make_msg(m.REJECT, key=list(key)))
        elif not self.in_election or key > self.wave:
            if self.in_election:
                self.log.warn(f"⚡ ONDA ABSORVIDA! Abandonando {self.wname(self.wave)} por "
                              f"{self.wname(key)} vinda de sta{sender}")
            self.log.info(f"📥 RECV PROBE de sta{sender} | Pai aceito: sta{sender}")
            self.join_wave(key, sender, budget)
        else:
            reason = "ciclo na árvore" if key == self.wave else "onda de menor prioridade"
            self.log.error(f"🚫 REJECT -> sta{sender} ({reason})")
            self.node.send_hop(sender, make_msg(m.REJECT, key=list(key)))

    def _reply_ok(self, sender, key):
        return self.in_election and key == self.wave and sender in self.pending

    def on_echo(self, sender, msg):
        key = tuple(msg["key"])
        if not self._reply_ok(sender, key):
            return
        self.pending.discard(sender)
        cand = tuple(msg["best"])
        if cand > self.best:
            self.best = cand
        self.children[sender] = set(msg["members"])
        self.members |= self.children[sender]
        self.prior = self.prior or bool(msg.get("prior"))
        self.log.ok(f"📥 RECV ECHO de sta{sender} | Pendentes: {len(self.pending)}")
        if not self.pending:
            self.finish_wave()

    def on_reject(self, sender, msg):
        key = tuple(msg["key"])
        if not self._reply_ok(sender, key):
            return
        self.pending.discard(sender)
        self.log.error(f"📥 RECV REJECT de sta{sender} | Pendentes: {len(self.pending)}")
        if not self.pending:
            self.finish_wave()

    def on_announce(self, sender, msg):
        key, leader = tuple(msg["key"]), msg["leader"]
        if not (self.in_election and key == self.wave and sender == self.parent):
            return
        self.node.leader = leader
        self.in_election = False
        self.closed.add(key)
        self.announce_prior = bool(msg.get("prior"))
        self.log.ok(f"📢 ANÚNCIO: O novo líder da rede é sta{leader}! "
                    f"(recebido do pai sta{sender})", bold=True)
        self.forward_announce(key, leader, self.announce_prior)
        self.after_announce()

    # ----------------------------------------------------------------- timers
    def on_wave_timeout(self, key):
        if self.in_election and self.wave == key and self.pending:
            lost = ", ".join(f"sta{x}" for x in sorted(self.pending))
            self.log.error(f"⏰ Prazo da onda {self.wname(key)} estourou: sem resposta de {lost} "
                           f"(tratados como falhos/inalcançáveis).")
            self.pending.clear()
            self.finish_wave()

    def on_wave_expire(self, key):
        if self.in_election and self.wave == key:
            self.log.error(f"⏰ Onda {self.wname(key)} abandonada: ANNOUNCE não chegou.")
            self.in_election = False
            self.closed.add(key)
            if self.node.resources.has_requests():
                self.start_election("pedidos pendentes após onda abandonada")
