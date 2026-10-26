# Casa de Leilões

Teste técnico Elite Dev (Verzel). O back-end está completo: cadastro e login por papel, busca de
itens no Met com cache, criação de lote com snapshot e imagem guardados no banco, carteira com
depósito, lances com todas as regras do enunciado sob concorrência, encerramento automático com
liquidação e comprovante, e auditoria pública do histórico de cada lote. A interface, o tempo real
(WebSocket) e o seed chegam nas próximas etapas. Por enquanto, a página inicial mostra o status da API.

## Estrutura

- `backend/`: FastAPI assíncrono, SQLAlchemy, psycopg e Alembic. Domínio em `app/services/`
  (núcleo puro em `regras.py`, `cadeia.py` e `verificacao.py`), rotas em `app/api/`.
- `frontend/`: React, Vite, Tailwind, React Router e React Query.
- `docker-compose.yml`: PostgreSQL 17, API e frontend servido por nginx.

## Docker Compose

Com Docker e o plugin Compose instalados, na raiz:

```sh
docker compose up --build
```

Acesse <http://localhost:8080>. O nginx encaminha `/api/` para o backend; o health check está em
<http://localhost:8080/api/health> e a documentação da API em <http://localhost:8080/api/docs>.
O backend executa `alembic upgrade head` antes de iniciar (migration `0001_inicial`).
O banco persiste no volume `pgdata`; `docker compose down` encerra os serviços sem apagar os dados.
As credenciais `leilao`/`leilao` são exclusivas de desenvolvimento local.

## Desenvolvimento

Requisitos: Python 3.12, uv, Node.js 24, npm e Docker Compose para o PostgreSQL.
Na raiz, inicie o banco (porta 5432 publicada somente em loopback; se ela já estiver ocupada, use
`DB_PORT=5433 docker compose up -d db` e ajuste a porta em `backend/.env`):

```sh
docker compose up -d db
```

Em outro terminal, a partir da raiz:

```sh
cd backend
cp .env.example .env
uv sync --locked
# Gere duas chaves distintas e mantenha-as fora do banco e do repositório:
export CHAVE_INTEGRIDADE="$(uv run python -c 'import secrets; print(secrets.token_hex(32))')"
export CHAVE_PRIVACIDADE="$(uv run python -c 'import secrets; print(secrets.token_hex(32))')"
export CORS_ORIGINS=http://localhost:5173,http://localhost:8080
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

O backend lê `backend/.env` quando iniciado nessa pasta; variáveis de ambiente têm prioridade.
O Compose define os valores dos containers diretamente. `CORS_ORIGINS` recebe as origens separadas
por vírgula, e `DATABASE_URL` aceita `postgres://`, `postgresql://` ou `postgresql+psycopg://`.
`CHAVE_INTEGRIDADE` e `CHAVE_PRIVACIDADE` são obrigatórias: hexadecimal com no mínimo 32 bytes.
Guarde as chaves geradas em configuração privada persistente antes de criar dados; trocar a chave
de integridade torna os históricos existentes inválidos e trocar a de privacidade muda pseudônimos.
O Compose usa chaves públicas exclusivamente locais. Com `ENVIRONMENT=production`, a aplicação
recusa essas chaves públicas e duas chaves iguais; o cookie de sessão passa a exigir HTTPS.

Requisições POST/PUT/PATCH/DELETE sob `/api/` exigem origem permitida. O padrão local permite
`http://localhost:5173`; o Compose permite `http://localhost:8080`. O export acima libera ambas
no desenvolvimento local. Em clientes de linha de comando com o Compose, envie
`-H 'Origin: http://localhost:8080'`; com a configuração local padrão, use
`-H 'Origin: http://localhost:5173'`. Depósitos e lances exigem também
`-H 'Idempotency-Key: uma-chave-unica'` (8 a 128 letras ASCII, números, `_` ou `-`).

Em outro terminal, a partir da raiz:

```sh
cd frontend
npm ci
npm run dev
```

Acesse <http://localhost:5173>. O Vite encaminha `/api` e `/ws` para a API local na porta 8000.
O proxy de WebSocket está preparado, mas ainda não há endpoint WebSocket.
O health check e os testes não precisam do PostgreSQL.

## Testes, lint e build

No backend:

```sh
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run alembic heads
uv run alembic upgrade head --sql
```

A suíte sem banco usa o núcleo puro e HTTP simulado; os testes `pg` são pulados com o motivo
`defina TEST_DATABASE_URL`. Para executar a suíte inteira, defina uma URL PostgreSQL cujo nome de
banco termine em `_test`, no mesmo formato de `DATABASE_URL`, e rode `uv run pytest`.
Os testes criam esse banco quando faltar e executam `TRUNCATE` antes de cada caso `pg`.
Nunca use banco com dados reais. URL presente com banco inacessível encerra a suíte com erro.
O usuário precisa de permissão para criar o banco de teste via conexão ao banco `postgres`.

No sandbox sem rede/Postgres, use `UV_CACHE_DIR=/tmp/verzel-uv-cache TMPDIR=/tmp` e
`uv run --offline --no-sync pytest -p no:cacheprovider`; os checks do Ruff e do Alembic aceitam
o mesmo prefixo. A validação de concorrência, migration e liquidação exige a suíte `pg` fora do sandbox.

No frontend:

```sh
cd frontend
npm run typecheck
npm test
npm run build
```

O frontend usa a checagem estrita do TypeScript; não há script de lint separado nesta etapa.
Na raiz, `docker compose config` valida a configuração dos serviços.

## Notas do back-end

- Valores monetários são centavos inteiros. Carteiras, razão e reservas são alterados sob travas
  PostgreSQL, na ordem lote → carteiras por id; o relógio do lance é lido depois das travas.
- “Valor mínimo” no painel significa lance inicial. Nos últimos dois minutos, o fim passa a ser
  o instante do lance mais 120 segundos, sem nunca recuar; com exatos 120 segundos, ele fica igual.
- Só leiloeiros criam/cancelam lotes; só licitantes depositam/dão lances. Cancelamento aceita
  apenas lote sem lance, portanto não há estorno. Lote cancelado não aparece na vitrine.
- A mesma chave idempotente com a mesma entrada devolve o sucesso original, mesmo após superação
  ou encerramento, com `Idempotency-Replayed: true`. Outra entrada dá 409. Recusas não consomem a chave;
  repeti-las reavalia as regras. Uma falha de comunicação pode ser repetida com a mesma chave.
- O worker encerra lotes vencidos; o detalhe também tenta encerrar e espera a trava em uso.
  Em instância que dorme, a liquidação ocorre quando o processo acorda. Lotes bloqueados por
  integridade da cadeia ou divergência entre carteira e razão aparecem como encerrados, sem
  resultado, e retêm a reserva do líder até intervenção manual. Saem da fila em memória;
  reiniciar reavalia uma vez. O log crítico distingue cadeia inválida de carteira divergente.
- A auditoria pública confere uma cadeia HMAC-SHA-256 e sua cabeça autenticada, com pseudônimos
  específicos por lote: eventos, snapshot, mídia, projeções, reserva, liquidação e seus lançamentos.
  Saldos, depósitos, usuários e papéis ficam fora dessa verificação; a auditoria pode dizer
  `integro` para um lote cuja liquidação foi bloqueada por divergência na carteira.
  Detecta mudanças, inserções e remoções parciais no banco. Não detecta a
  restauração de um estado antigo inteiro autenticado, e apagar o lote inteiro resulta em 404.
  Uma âncora externa seria necessária para detectar restauração completa em produção.
  Um salto para trás no relógio do banco entre eventos do mesmo lote pode produzir um falso
  resultado `adulterado`, pois a verificação exige instantes em ordem não decrescente.
- Snapshot e imagem ficam no PostgreSQL. Met indisponível não afeta vitrine, detalhe, carteira,
  comprovante ou auditoria; a busca usa cache disponível e indica sua origem. Criar lote exige
  acesso ao Met, salvo quando o item e a imagem já estão em cache. A busca fatia os ids antes de
  filtrar itens elegíveis de domínio público: uma página pode ter menos de 20 itens, ou estar
  vazia, mesmo com `tem_mais=true`.
- WebSocket e seed são etapas seguintes. O publicador pós-commit já existe; tempo real pressupõe
  um único processo da aplicação. Falha de notificação não desfaz uma operação financeira aceita.
