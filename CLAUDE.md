# Casa de Leilões

Casa de leilões online. O leiloeiro cria lotes a partir de itens do acervo aberto do Metropolitan
Museum, e os licitantes disputam com lances ao vivo usando uma carteira simulada. O arremate gera um
comprovante público, e cada lote tem uma auditoria pública que detecta adulteração feita direto no
banco. Monorepo com `backend/` (FastAPI, SQLAlchemy assíncrono, PostgreSQL), `frontend/` (React,
Vite, Tailwind) e `docker-compose.yml`.

## Comandos

```sh
# backend/
uv sync --locked
uv run pytest                      # sem banco, os testes marcados `pg` são pulados
uv run ruff check . && uv run ruff format --check .

# testes com PostgreSQL (na raiz: docker compose up -d db)
TEST_DATABASE_URL=postgresql+psycopg://leilao:leilao@localhost:5432/leilao_test uv run pytest

# frontend/
npm ci
npm run typecheck && npm test && npm run build

# raiz: app em http://localhost:8080, documentação da API em /api/docs
docker compose up --build
```

O banco de teste precisa terminar em `_test`, porque a suíte trunca as tabelas.

## Arquitetura do back-end

- `app/services/regras.py`, `cadeia.py` e `verificacao.py` são o núcleo puro, sem I/O. Regras de
  lance e fases, envelope canônico com HMAC e pseudônimo, e verificação da cadeia.
- `app/services/lances.py`, `liquidacao.py`, `encerramento.py`, `lotes.py`, `carteira.py`,
  `idempotencia.py`, `consultas.py`, `auth.py`, `itens.py` e `notificacoes.py` fazem o I/O em cima
  do núcleo.
- `app/api/` tem rotas finas. `app/schemas/` tem os contratos Pydantic, com entrada em
  `extra="forbid"`. `app/models/` usa SQLAlchemy sem relationships.
- `alembic/versions/0001_inicial.py` é escrita à mão e precisa bater com a metadata
  (`tests/test_migracao.py` confere).
- `app/recursos.py` abre no lifespan o engine, o cliente HTTP, o cache, o publicador e o worker de
  encerramento. Os testes injetam recursos próprios.
- `app/db/transacao.py` executa uma transação por comando, com `lock_timeout` de 3 s e retentativa da
  transação inteira em deadlock (`40P01`) ou timeout de trava (`55P03`). Leituras consistentes usam
  `REPEATABLE READ READ ONLY`.
- Erros seguem o contrato `{"erro": {"codigo", "mensagem", "detalhes"}}`, com códigos estáveis em
  `app/core/erros.py`.
- Tempo real: `app/api/tempo_real.py` (rota `/ws`) e `app/services/tempo_real.py` (central em memória,
  que é o publicador pós-commit). A mensagem é só um sinal (`v`, `tipo`, `lote_id`, `versao`), e o
  front refaz o GET. `carteira_atualizada` vai só às conexões do próprio usuário. Handshake: `Origin`
  antes de tocar no banco, cookie `sessao`, revalidação periódica, e logout fecha a conexão com 4001.
- `app/demo/` é o seed de demonstração (`SEED_DEMO=true`): roda no startup e a cada hora, sob trava
  consultiva, só pelos serviços do núcleo, com chaves idempotentes estáveis. Snapshots e imagens dos
  itens ficam em `app/demo/dados/`, sem depender do Met. `python -m app.demo` roda uma vez.
- `app/web/spa.py` serve o build do front pela própria API quando `FRONTEND_DIST` está definido (deploy
  num único processo e numa única origem). Localmente, o compose usa o nginx do container do front.

## Arquitetura do front-end

- `src/api/`: cliente HTTP (`http.ts`), tipos espelhando `backend/app/schemas` (`tipos.ts`), leituras
  e mutações do React Query, e `sessao.ts`, que concentra a troca de identidade.
- Toda troca de identidade (login, cadastro, logout, sessão expirada) passa por `trocarIdentidade`:
  incrementa uma geração, cancela leituras, zera os dados pessoais, remonta as rotas e reinicia o
  WebSocket. Mutação iniciada numa geração anterior não toca o cache.
- `src/lib/`: dinheiro (`dinheiro.ts`, parse de reais por string, sem float), mensagens por código de
  erro (`erros.ts`), relógio do servidor (`relogio.ts`), fases, datas, tema e chave idempotente.
- `src/tempoReal/`: conexão com reconexão e despachante de invalidações.
- O relógio vem do servidor (`servidor_agora` ou cabeçalho `Date`), nunca do navegador.

## Regras do enunciado

- Lance só com o lote ao vivo. O primeiro precisa ser maior ou igual ao inicial, e os seguintes
  maiores ou iguais ao atual mais o incremento.
- O líder não cobre o próprio lance, e o leiloeiro não dá lance.
- O lance precisa caber no saldo disponível (total menos comprometido). Quem é superado recebe o
  comprometido de volta na hora.
- Lance nos últimos 2 minutos faz o fim passar a ser o instante do lance mais 2 minutos
  (`fim_novo = max(fim_em, instante + 120 s)`).
- A liquidação debita o vencedor e credita o leiloeiro. Lote sem lance fecha sem vencedor.
- O leiloeiro só cancela lote sem lance, e lote cancelado não aparece na vitrine.
- "Valor mínimo" no painel do leiloeiro é o lance inicial.
- O seed traz um leiloeiro, dois licitantes e ao menos um lote ao vivo com lances.

## Invariantes do código

- Dinheiro é centavo inteiro (`int` e `BIGINT`), nunca `float`. Entrada de dinheiro é estrita.
- Ordem de travas: o lote antes de qualquer carteira, e as carteiras em ordem crescente de id. O
  instante do lance é `clock_timestamp()`, lido depois das travas.
- O saldo de cada carteira é a soma dos seus lançamentos. O disponível é o saldo menos as reservas, e
  existe no máximo uma reserva por lote, a do líder.
- Toda escrita sobre um lote (lance, cancelamento, encerramento) roda antes a verificação completa da
  cadeia. Se falhar, a resposta é 409 `lote_adulterado` e nada é gravado. A liquidação só move
  dinheiro com as duas carteiras reconciliadas com o razão.
- Auditoria: cadeia de eventos por lote autenticada com HMAC-SHA-256 e cabeça autenticada com domínio
  distinto. Escrita e verificação montam o envelope pela mesma função. As chaves `CHAVE_INTEGRIDADE` e
  `CHAVE_PRIVACIDADE` ficam fora do banco, e em produção a API recusa as de desenvolvimento.
- Limite aceito da auditoria: restaurar um estado antigo inteiro (eventos, projeções, reserva e
  cabeça) não é detectado. Só uma âncora externa resolveria. Está no README.
- Resposta pública não expõe nome, e-mail nem id interno. O licitante aparece pelo pseudônimo HMAC do
  lote.
- Papel e identidade vêm só da sessão. POST exige `Origin` permitido. Lance e depósito exigem
  `Idempotency-Key`.
- Notificação sai só depois do commit, e falha nela não desfaz a operação.
- Nenhuma chamada HTTP externa com transação aberta. Com o Met fora do ar, vitrine, detalhe,
  auditoria, comprovante, mídia e carteira continuam respondendo pelo banco.

## API do Met

- Busca em `/public/collection/v1.1/search` (a `v1/search` responde 410).
- Detalhe em `/public/collection/v1/objects/{id}` (a `v1.1/objects` responde 404).
- A busca ignora `page` e `pageSize` e devolve todos os `objectIDs`, então a paginação fatia a lista.
  `objectIDs` vem `null` quando não há resultado.
- Só entram itens com `isPublicDomain: true` e `primaryImageSmall`, com a imagem em
  `images.metmuseum.org`.

## Escopo

- Cancelamento com estorno fica fora, porque só se cancela lote sem lance.
- O WebSocket roda no mesmo processo, com um único worker de aplicação. Mais de um worker
  dividiria as conexões entre centrais que não se falam.
- As contas de demonstração são públicas (senha no README e em `GET /api/demo`, que alimenta o
  acesso rápido do login). Elas controlam os lotes e reservas do seed, e o seed repõe saldo e lotes,
  mas não desfaz lance de visitante.

## Convenções

- Identificadores, mensagens e documentação em PT-BR. Seguir o estilo do código ao redor.
- Testes de concorrência e de adulteração rodam contra PostgreSQL real (marcador `pg`), nunca com
  SQLite ou mock de banco.
- Comportamento inesperado e limites conhecidos vão para o README.
