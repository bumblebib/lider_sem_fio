"""Gerencia os processos dos nós. crash = kill real; recover = processo novo."""

import multiprocessing
import time

from cli.client import collect_status
from colors import C_RED, C_RESET
from config import GRAPH
from node.node import run_node_process


class Cluster:
    def __init__(self, step_delay):
        self.step_delay = step_delay
        self.ctx = multiprocessing.get_context("spawn")
        self.procs = {}

    def start(self, node_id):
        proc = self.ctx.Process(target=run_node_process,
                                args=(node_id, GRAPH[node_id], self.step_delay), daemon=True)
        proc.start()
        self.procs[node_id] = proc

    def start_all(self):
        for node_id in GRAPH:
            self.start(node_id)

    def running(self, node_id):
        proc = self.procs.get(node_id)
        return proc is not None and proc.is_alive()

    def kill(self, node_id):
        if not self.running(node_id):
            print(f"sta{node_id} já está inativo.")
            return
        self.procs[node_id].kill()
        self.procs[node_id].join()
        print(f"{C_RED}💥 sta{node_id} MORTO (processo encerrado de verdade, socket fechado).{C_RESET}")

    def wait_ready(self, ids, timeout=10.0):
        ids = list(ids)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(collect_status(ids, wait=0.3)) == len(ids):
                return True
        return False

    def stop_all(self):
        for proc in self.procs.values():
            if proc.is_alive():
                proc.kill()
