"""Configuração global: rede, topologia, capacidades e prazos.

Para mudar a topologia ou as capacidades, edite apenas este arquivo.
"""

HOST = "127.0.0.1"
BASE_PORT = 5000
LOGGER_PORT = 6000
DEFAULT_STEP_DELAY = 0.3  # atraso por salto, só para dar para acompanhar no terminal (0 desliga)

GRAPH = {
    1:  [2, 4],
    2:  [1, 3, 5],
    3:  [2, 6],
    4:  [1, 5, 8],
    5:  [2, 4, 6, 8, 9],
    6:  [3, 5, 7, 9, 10],
    7:  [6, 10],
    8:  [4, 5, 9],
    9:  [5, 6, 8, 10],
    10: [6, 7, 9],
}
N = len(GRAPH)
CAPACITY = {i: i * 10 for i in GRAPH}  # edite para outras capacidades


def _check_graph():
    for a, neigh in GRAPH.items():
        for b in neigh:
            assert a in GRAPH[b], f"aresta {a}-{b} não é simétrica"


def _diameter():
    best = 0
    for start in GRAPH:
        dist, queue = {start: 0}, [start]
        for u in queue:
            for v in GRAPH[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    queue.append(v)
        best = max(best, max(dist.values()))
    return best


_check_graph()
DIAMETER = _diameter()


class Timing:
    """Prazos derivados do atraso por salto e do diâmetro do grafo."""

    def __init__(self, step_delay):
        self.step_delay = step_delay
        hop_rtt = 2 * step_delay + 0.4                      # ida + volta de um salto, com folga
        self.hop_slack = hop_rtt                            # quanto o orçamento encolhe por nível
        self.wave_budget = (DIAMETER + 2) * hop_rtt + 1.0   # prazo da raiz para juntar os ECHOs
        self.announce_grace = N * (step_delay + 0.2) + 1.0  # espera extra pelo ANNOUNCE
        self.request_timeout = 2 * (DIAMETER + 2) * (step_delay + 0.1) + 1.0
        self.register_window = 2 * (DIAMETER + 2) * (step_delay + 0.1) + 0.5
