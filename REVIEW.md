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

## Testes exigidos

- Regra de lance nova ou alterada: teste puro em `tests/test_regras.py` com a fronteira (o valor
  exato aceito, um centavo a menos recusado).
- Escrita concorrente: teste `pg` com tarefas simultâneas, terminando em `conferir_reconciliacao`.
  Teste de concorrência não pode passar só por causa da retentativa (o contador de deadlocks do
  banco não pode subir).
- Proteção nova contra adulteração: caso em `tests/test_auditoria_adulteracao.py` com o código de
  falha esperado, e um teste que falhe se a proteção for removida.
- Rota nova: código de erro e formato da resposta conferidos pelo cliente HTTP de teste.

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
