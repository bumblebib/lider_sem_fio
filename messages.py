"""Tipos de mensagem do protocolo e helper para montá-las."""

# Eleição (só entre vizinhos)
PROBE = "PROBE"
ECHO = "ECHO"
REJECT = "REJECT"
ANNOUNCE = "ANNOUNCE"

# Exclusão mútua (roteadas salto a salto pela árvore)
REQ_RESOURCE = "REQ_RESOURCE"
REL_RESOURCE = "REL_RESOURCE"
REGISTER_HELD = "REGISTER_HELD"
GRANT_RESOURCE = "GRANT_RESOURCE"
WAIT_RESOURCE = "WAIT_RESOURCE"

# Controle (CLI -> nó)
CTRL_PREFIX = "CTRL_"
CTRL_ELECT = "CTRL_ELECT"
CTRL_RESOURCE = "CTRL_RESOURCE"
CTRL_RELEASE = "CTRL_RELEASE"
CTRL_STATUS = "CTRL_STATUS"
STATUS_RESP = "STATUS_RESP"

ROUTED_TYPES = frozenset({REQ_RESOURCE, REL_RESOURCE, REGISTER_HELD, GRANT_RESOURCE, WAIT_RESOURCE})
LEADER_ONLY = frozenset({REQ_RESOURCE, REL_RESOURCE, REGISTER_HELD})


def make_msg(msg_type, **fields):
    """Monta uma mensagem do protocolo: {"type": ..., **campos}."""
    return {"type": msg_type, **fields}
