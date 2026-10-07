"""Comandos do terminal: parsing, handlers e laço de leitura."""

import re
import time

import messages as m
from cli.client import query_status_all, send_control_msg
from colors import C_BOLD, C_CYAN, C_RESET
from config import N

HELP = f"""
{C_BOLD}Comandos Disponíveis:{C_RESET}
  {C_CYAN}recurso <no> [recurso] ...{C_RESET}    : Solicita acesso a recursos.
                                   Ex: recurso 1 R1 2 R2
                                   Ex: recurso 1 7 R1
  {C_CYAN}liberar <no> [recurso] ...{C_RESET}    : Libera recurso mantido por nó(s).
                                   Ex: liberar 1 R1
  {C_CYAN}eleicao <id1> [id2...]{C_RESET}        : Força início manual de eleição.
  {C_CYAN}crash <id> [id2...]{C_RESET}           : Mata o processo do nó (falha real).
  {C_CYAN}recover <id> [id2...]{C_RESET}         : Sobe um processo novo para o nó.
  {C_CYAN}status{C_RESET}                        : Tabela de nós, árvore, recursos e PIDs do SO.
  {C_CYAN}espera <segundos>{C_RESET}             : Pausa entre comandos encadenados com ";".
                                   Ex: eleicao 9; espera 0.7; eleicao 2
  {C_CYAN}sair{C_RESET}                          : Encerra a aplicação.
  (nós: 1..{N} ou sta1..sta{N}; vários comandos na mesma linha: separe com ";")
"""


class Quit(Exception):
    """Sinaliza que o usuário pediu para sair."""


# ----------------------------------------------------------------------- parsing
def parse_node(token):
    match = re.fullmatch(r"(?:sta)?(\d+)", token.lower())
    if match and 1 <= int(match.group(1)) <= N:
        return int(match.group(1))
    return None


def parse_node_resource_pairs(args):
    nodes_acc, pairs = [], []
    for arg in args:
        node = parse_node(arg)
        if node is not None:
            nodes_acc.append(node)
        elif re.fullmatch(r"[A-Za-z]\w*", arg):
            pairs.extend((n, arg.upper()) for n in nodes_acc)
            nodes_acc = []
        else:
            print(f"Ignorado: '{arg}' não é um nó (1..{N}) nem um nome de recurso.")
    pairs.extend((n, "R1") for n in nodes_acc)
    return pairs


def parse_ids(args, usage):
    ids = [parse_node(x) for x in args]
    if not ids or None in ids:
        print(f"Uso: {usage} (nós 1..{N})")
    return [i for i in ids if i is not None]


# ---------------------------------------------------------------------- handlers
def cmd_recurso(cluster, args):
    pairs = parse_node_resource_pairs(args)
    if not pairs:
        print("Informe ao menos um nó! Ex: recurso 1 R1 ou recurso 1 R1 2 R2")
    for node_id, res in pairs:
        send_control_msg(node_id, m.CTRL_RESOURCE, {"resource": res})


def cmd_liberar(cluster, args):
    pairs = parse_node_resource_pairs(args)
    if not pairs:
        print("Informe qual nó vai liberar o recurso! Ex: liberar 1 R1")
    for node_id, res in pairs:
        send_control_msg(node_id, m.CTRL_RELEASE, {"resource": res})


def cmd_eleicao(cluster, args):
    for node_id in parse_ids(args, "eleicao <no> [no ...]"):
        send_control_msg(node_id, m.CTRL_ELECT)


def cmd_crash(cluster, args):
    for node_id in parse_ids(args, "crash <no> [no ...]"):
        cluster.kill(node_id)


def cmd_recover(cluster, args):
    for node_id in parse_ids(args, "recover <no> [no ...]"):
        if cluster.running(node_id):
            print(f"sta{node_id} já está ativo.")
        else:
            cluster.start(node_id)
            cluster.wait_ready([node_id])


def cmd_status(cluster, args):
    query_status_all()


def cmd_espera(cluster, args):
    try:
        time.sleep(max(0.0, float(args[0])))
    except (IndexError, ValueError):
        print("Uso: espera <segundos>   Ex: eleicao 9; espera 0.7; eleicao 2")


def cmd_ajuda(cluster, args):
    print(HELP)


def cmd_sair(cluster, args):
    raise Quit


COMMANDS = {
    "recurso": cmd_recurso, "usar_recurso": cmd_recurso,
    "liberar": cmd_liberar, "release": cmd_liberar,
    "eleicao": cmd_eleicao, "elect": cmd_eleicao,
    "crash": cmd_crash,
    "recover": cmd_recover,
    "status": cmd_status,
    "espera": cmd_espera, "sleep": cmd_espera,
    "ajuda": cmd_ajuda, "help": cmd_ajuda,
    "sair": cmd_sair, "exit": cmd_sair,
}


# ------------------------------------------------------------------ laço de leitura
def run_cli(cluster):
    """Lê comandos até o usuário sair (ou Ctrl+C / Ctrl+D) e então encerra os nós."""
    queue = []  # comandos encadeados com ";" na mesma linha
    while True:
        try:
            if not queue:
                queue = [c.strip() for c in input("> ").split(";") if c.strip()]
                if not queue:
                    continue
            parts = queue.pop(0).split()
            handler = COMMANDS.get(parts[0].lower())
            if handler is None:
                print("Comando inválido. Digite 'ajuda' para listar.")
                continue
            handler(cluster, parts[1:])
        except Quit:
            print("Encerrando...")
            break
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrando...")
            break
    cluster.stop_all()
