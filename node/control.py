"""Mensagens de controle vindas da CLI (CTRL_*): eleição manual, recursos e status."""

import json
import os

import messages as m


class Control:
    def __init__(self, node):
        self.node = node
        self.log = node.log
        self._handlers = {
            m.CTRL_ELECT: self._elect,
            m.CTRL_RESOURCE: self._resource,
            m.CTRL_RELEASE: self._release,
            m.CTRL_STATUS: self._status,
        }

    def on_control(self, msg, addr):
        handler = self._handlers.get(msg["type"])
        if handler:
            handler(msg, addr)

    def _elect(self, msg, addr):
        n, e = self.node, self.node.election
        potential = (n.capacity, n.id, e.epoch + 1)
        if e.in_election and e.wave[1] == n.id:
            self.log.warn(f"⚠️ Ordem de eleição ignorada: minha onda {e.wname(e.wave)} já está em curso.")
        elif e.in_election and e.wave > potential:
            self.log.warn(f"⚠️ Ordem de eleição ignorada: já participo da onda {e.wname(e.wave)}, "
                          f"de maior prioridade.")
        else:
            e.start_election("ordem manual")

    def _resource(self, msg, addr):
        self.node.resources.request_resource(msg.get("resource", "R1"))

    def _release(self, msg, addr):
        self.node.resources.release_resource(msg.get("resource", "R1"))

    def _status(self, msg, addr):
        n, e, r = self.node, self.node.election, self.node.resources
        status = {
            "id": n.id, "pid": os.getpid(), "alive": True,
            "status": "ELECTING" if e.in_election else "NORMAL",
            "leader": f"sta{n.leader}" if n.leader else None,
            "capacity": n.capacity,
            "parent": e.parent, "children": sorted(e.children),
            "held": sorted(r.held),
            "pending": sorted(r.pending_req | r.waiting_req),
        }
        try:
            n.sock.sendto(json.dumps({"type": m.STATUS_RESP, "data": status}).encode(), addr)
        except OSError:
            pass
