"""Cliente de controle: fala com os nós por UDP (ordens e consulta de status)."""

import json
import select
import socket
import time

import messages as m
from colors import C_BOLD, C_GREEN, C_RED, C_RESET
from config import BASE_PORT, CAPACITY, GRAPH, HOST


def send_control_msg(target_id, ctrl_type, extra_fields=None):
    payload = m.make_msg(ctrl_type, **(extra_fields or {}))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(json.dumps(payload).encode(), (HOST, BASE_PORT + target_id))


def collect_status(ids, wait=0.6):
    """Pergunta o status a vários nós de uma vez; quem não responde (processo morto) fica de fora."""
    results = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for i in ids:
            sock.sendto(json.dumps(m.make_msg(m.CTRL_STATUS)).encode(), (HOST, BASE_PORT + i))
        deadline = time.monotonic() + wait
        while len(results) < len(ids) and time.monotonic() < deadline:
            ready, _, _ = select.select([sock], [], [], max(0.0, deadline - time.monotonic()))
            if not ready:
                break
            try:
                data, _ = sock.recvfrom(4096)
                info = json.loads(data.decode())["data"]
                results[info["id"]] = info
            except (OSError, ValueError, KeyError):
                continue
    return results


def query_status_all():
    got = collect_status(list(GRAPH))
    head = (f"{'NÓ':<6} {'PID':<7} {'STATUS':<9} {'CAP':<4} {'LÍDER':<7} {'PAI':<5} "
            f"{'FILHOS':<12} {'RECURSOS':<10} {'PENDENTES':<10}")
    print(f"\n{C_BOLD}{head}{C_RESET}")
    print("-" * len(head))
    for i in GRAPH:
        r = got.get(i)
        if r is None:
            print(f"sta{i:<3} {'-':<7} {C_RED}{'DEAD':<9}{C_RESET} {CAPACITY[i]:<4} "
                  f"{'-':<7} {'-':<5} {'-':<12} {'-':<10} {'-':<10}")
            continue
        parent = f"sta{r['parent']}" if r["parent"] else "-"
        kids = ",".join(str(c) for c in r["children"]) or "-"
        print(f"sta{i:<3} {r['pid']:<7} {C_GREEN}{r['status']:<9}{C_RESET} {r['capacity']:<4} "
              f"{str(r['leader'] or '-'):<7} {parent:<5} {kids:<12} "
              f"{','.join(r['held']) or '-':<10} {','.join(r['pending']) or '-':<10}")
    print("-" * len(head) + "\n")
