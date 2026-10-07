# Eleição em árvore + exclusão mútua centralizada

Cada nó é um processo do SO com socket UDP em `127.0.0.1:(5000 + id)`. Só há
comunicação entre vizinhos; pedidos de recurso são roteados pela árvore criada
na eleição.

## Estrutura

```
eleicao_arvore/
├── main.py            # ponto de entrada (argparse + sobe cluster + CLI)
├── config.py          # HOST, portas, GRAPH, CAPACITY, DIAMETER, Timing
├── colors.py          # códigos ANSI
├── messages.py        # tipos de mensagem + make_msg()
├── logger.py          # NodeLog (nó) e logger_listener (terminal)
├── node/
│   ├── node.py        # Node: sockets, outbox, timers, dispatch, run_node_process
│   ├── election.py    # PROBE / ECHO / REJECT / ANNOUNCE
│   ├── routing.py     # roteamento salto a salto pela árvore
│   ├── resources.py   # exclusão mútua (cliente + líder)
│   └── control.py     # ordens da CLI (CTRL_*)
└── cli/
    ├── cluster.py     # start / kill / recover dos processos
    ├── client.py      # envio de ordens e consulta de status
    └── commands.py    # comandos do terminal e laço de leitura
```

## Executar

Requer Python 3.8+ (só biblioteca padrão). Dentro da pasta `eleicao_arvore/`:

```
python3 main.py              # atraso de 0.3 s por salto (bom para acompanhar)
python3 main.py --delay 0    # sem atraso
```

## Exemplo de uso

```
> eleicao 1
> status
> recurso 3 R1
> recurso 4 R1
> liberar 3 R1
> crash 10
> recover 10
> eleicao 9; espera 0.7; eleicao 2
> sair
```

Digite `ajuda` para ver todos os comandos. Para mudar topologia ou
capacidades, edite `config.py`.
