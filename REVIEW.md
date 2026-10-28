# Diretrizes de revisão

Este arquivo orienta a revisão de código neste repositório. As regras de negócio e as invariantes
estão no `CLAUDE.md`, e a revisão parte delas.

## Prioridade

1. Regras de lance e de dinheiro.
2. Concorrência e integridade da auditoria.
3. Segurança e privacidade.
4. Contrato da API com o front-end (rotas, nomes de campo, códigos de erro).
5. O resto.

## Sempre conferir

- **Dinheiro**: nenhum `float` no caminho de valores. Agregados do PostgreSQL (`SUM`) convertidos
  para `int`. Débito e crédito da liquidação somam zero e acontecem uma única vez por lote.
- **Travas**: escrita nova em lote ou carteira segue a ordem lote → carteiras por id crescente. Nada
  trava um lote depois de uma carteira, e o relógio é lido depois da última trava.
- **Transação**: nenhuma chamada HTTP externa com transação aberta. A retentativa refaz a transação
  inteira, sem efeito duplicado.
- **Integridade**: toda escrita sobre um lote passa por `conferir_ponta` antes de gravar. Tipo novo
  de evento entra no envelope, na gramática e nas transições de `verificacao.py`.
- **Envelope e canonicalização**: qualquer mudança invalida as cadeias já gravadas. Sem migração
  dos dados, é bloqueante.
- **Idempotência**: recusa não grava a chave. A repetição devolve status e corpo idênticos ao
  original. Mesma chave com outra entrada dá 409.
- **Privacidade**: resposta pública sem nome, e-mail, id interno ou `cabeca_assinatura`.
- **Entrada**: schemas com `extra="forbid"`, centavos estritos, texto sem byte nulo e parâmetros de
  caminho com padrão.
- **Segredos**: chave HMAC nunca em log, banco ou resposta. O engine mantém `hide_parameters=True`.
- **Migration**: toda `CheckConstraint` tem nome, e a migration bate com a metadata.
- **WebSocket**: a mensagem continua só sinal, sem dado de domínio. `Origin` é conferido antes de
  qualquer acesso ao banco. Sinal privado só para o próprio usuário. Toda conexão registrada sai da
  central em qualquer caminho de falha, e logout ou sessão revogada fecha a conexão sem entregar o que
  estava na fila.
- **Seed**: só pelos serviços do núcleo, nunca `INSERT` ou `UPDATE` direto. Idempotente sob reinício
  e com dois processos. Nunca derruba a subida da aplicação.
- **SPA**: arquivo servido só a partir do que foi carregado na memória, nunca de caminho montado pela
  URL. `/api` e `/ws` nunca recebem HTML. `Referrer-Policy` fica `same-origin`, porque `no-referrer`
  pode mandar `Origin: null` e o CSRF recusa.
- **Front, dinheiro**: reais convertidos para centavos por string, sem `parseFloat`, `toFixed` ou
  `Math.round`. Valor fora de inteiro seguro mostra "valor inválido" e não derruba a tela.
- **Front, identidade**: toda troca de conta passa por `trocarIdentidade`. Nenhuma tela mostra dado
  da identidade anterior, e mutação de geração antiga não toca o cache.
- **Front, idempotência**: a chave é reaproveitada só quando a tentativa anterior ficou incerta, para o
  mesmo alvo e o mesmo valor.
- **Front, relógio**: contagem regressiva e fases pelo relógio do servidor.

## Testes exigidos

- Regra de lance nova ou alterada: teste puro em `tests/test_regras.py` com a fronteira (o valor
  exato aceito, um centavo a menos recusado).
- Escrita concorrente: teste `pg` com tarefas simultâneas, terminando em `conferir_reconciliacao`.
  Teste de concorrência não pode passar só por causa da retentativa (o contador de deadlocks do
  banco não pode subir).
- Proteção nova contra adulteração: caso em `tests/test_auditoria_adulteracao.py` com o código de
  falha esperado, e um teste que falhe se a proteção for removida.
- Rota nova: código de erro e formato da resposta conferidos pelo cliente HTTP de teste.
- WebSocket: o driver ASGI em processo (`tests/ws_asgi.py`) cobre handshake, isolamento e corridas sem
  socket real. O teste com uvicorn real fica marcado `pg`.
- Front: componente ou hook com lógica nova ganha teste no Vitest. Cabeçalho de segurança e texto de
  contrato se conferem por valor literal, nunca comparando com a constante do próprio código.

## Severidade

- **Crítico**: dinheiro criado ou perdido, liquidação em dobro, lance aceito fora das regras,
  adulteração não detectada fora do limite documentado, segredo exposto.
- **Alto**: deadlock ou erro 500 em fluxo normal, falso "adulterado" em lote íntegro, dado pessoal em
  resposta pública, quebra do contrato com o front-end.
- **Médio e baixo**: o resto, com cenário concreto de falha.

## Não apontar

- Formatação e ordem de imports (o `ruff` cuida).
- O limite documentado da auditoria (restauração de um estado antigo inteiro).
- Ausência de cancelamento com estorno (fora do escopo).
- Mensagens de validação do Pydantic em inglês dentro de `detalhes` (o front-end usa o código).
