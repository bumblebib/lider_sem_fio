#!/usr/bin/env python3
"""
main.py - Ponto de entrada: eleição em árvore (convergecast) + exclusão mútua centralizada.

Sobe um processo por nó (multiprocessing, método "spawn"), o logger central e a CLI.

Uso: python3 main.py [--delay SEGUNDOS]
"""

import argparse
import threading

from cli.cluster import Cluster
from cli.commands import run_cli
from colors import C_BOLD, C_CYAN, C_RESET
from config import DEFAULT_STEP_DELAY, GRAPH
from logger import logger_listener


def main():
    parser = argparse.ArgumentParser(description="Eleição em árvore + exclusão mútua centralizada")
    parser.add_argument("--delay", type=float, default=DEFAULT_STEP_DELAY,
                        help="atraso por salto em segundos, só para visualização (padrão 0.3; 0 desliga)")
    args = parser.parse_args()

    print(f"{C_BOLD}{C_CYAN}======================================================={C_RESET}")
    print(f"{C_BOLD}   ELEIÇÃO EM ÁRVORE + EXCLUSÃO MÚTUA DE RECURSOS   {C_RESET}")
    print(f"{C_BOLD}{C_CYAN}======================================================={C_RESET}")

    threading.Thread(target=logger_listener, daemon=True).start()

    cluster = Cluster(args.delay)
    cluster.start_all()
    if not cluster.wait_ready(GRAPH):
        print("Aviso: nem todos os nós responderam a tempo.")
    print("\nDigite 'ajuda' para listar os comandos disponíveis.\n")

    run_cli(cluster)


if __name__ == "__main__":
    main()
