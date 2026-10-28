# Casa de Leilões

Teste técnico Elite Dev (Verzel). Casa de leilões com vitrine, disputa ao vivo, carteira simulada,
painel do leiloeiro e contas de demonstração. Os itens vêm do acervo aberto do Metropolitan Museum;
snapshot e imagem ficam no banco. Lances respeitam saldo, incremento e prorrogação sob concorrência.
O encerramento liquida o arremate e gera comprovante compartilhável, com auditoria pública do histórico.
A interface tem tema claro e escuro, atualização por WebSocket e consultas periódicas quando a conexão cai.

## Estrutura

- `backend/`: FastAPI assíncrono, SQLAlchemy, psycopg e Alembic. Domínio em `app/services/`
  (núcleo puro em `regras.py`, `cadeia.py` e `verificacao.py`), rotas em `app/api/`.
  `app/demo/` contém catálogo local e seed; `app/web/` serve o build do SPA pela API quando configurado.
- `frontend/`: React, Vite, Tailwind, React Router e React Query. `src/api/` contém contratos e consultas;
  `lib/` e `hooks/` tratam dinheiro, relógio e identidade; `tempoReal/` cuida da conexão e invalidação;
  `components/` e `pages/` compõem as telas.
- `docker-compose.yml`: PostgreSQL 17, API e frontend servido por nginx.

## Docker Compose

Com Docker e o plugin Compose instalados, na raiz:

```sh
docker compose up --build
```

Acesse <http://localhost:8080>. O nginx encaminha `/api/` para o backend; o health check está em
<http://localhost:8080/api/health> e a documentação da API em <http://localhost:8080/api/docs>.
O backend executa `alembic upgrade head` antes de iniciar (migration `0001_inicial`).
O Compose habilita o seed no boot, com três contas públicas e quatro lotes descritos abaixo.
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
O endpoint `/ws` usa a sessão por cookie e valida a origem; os lances continuam sendo enviados por HTTP.
Para habilitar a demonstração no desenvolvimento local, inicie a API com `SEED_DEMO=true`.
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

A suíte sem banco usa o núcleo puro, HTTP simulado e um driver ASGI em processo para WebSocket
(sem socket local). Ela cobre handshake, isolamento dos sinais privados, logout, revalidação,
filas, SPA e planejamento do seed; os testes `pg` são pulados com o motivo
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
O Vitest cobre dinheiro, relógio, reconexão, ressincronização durante GET, idempotência dos envios,
troca de identidade com respostas pendentes e os fluxos das telas. O teste com uvicorn e WebSocket
real fica na suíte `pg`, junto da integração do seed com PostgreSQL.
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
- WebSocket e seed usam os serviços existentes e as notificações pós-commit. Tempo real pressupõe
  um único processo da aplicação. Falha de notificação não desfaz uma operação financeira aceita.

## Como usar

1. Na vitrine, busque uma obra pelo título e filtre lotes ao vivo, agendados ou encerrados. A sala
   mostra contagem pelo relógio do servidor, mínimo, histórico e posição na disputa.
2. Entre como comprador 1 e comprador 2 em dois navegadores. Deposite na carteira, dê um lance e cubra-o pela outra
   conta: a sala e o saldo reservado se atualizam. Um lance nos últimos dois minutos prorroga o fim,
   com aviso nas duas salas. O botão “Tentar de novo” conserva a chave de uma tentativa sem resposta.
3. Em “Meus arremates”, acompanhe disputas e resultados. O vencedor pode copiar o link público do
   comprovante. A auditoria abre sem login e informa integridade, eventos conferidos e eventual falha.
4. Entre como Leiloeiro para buscar itens no Met, selecionar uma obra e publicar um lote. O painel
   mostra resultados, comprovantes e total recebido; só lotes sem lance podem ser cancelados.
5. Desligue a rede no navegador para observar a reconexão e o retorno das consultas. Troque o tema
   pelo seletor do cabeçalho; a preferência acompanha o sistema até você escolher outra.

A API também pode servir o build: depois de `npm run build`, configure `FRONTEND_DIST` com o caminho
de `frontend/dist` e `CORS_ORIGINS` com a origem onde o uvicorn estará acessível. O Compose continua
usando nginx. O SPA carrega os arquivos em memória; `assets/` usa cache imutável e o HTML usa
`no-cache`. API e WebSocket nunca caem no fallback do HTML. A política `Referrer-Policy: same-origin`
evita enviar o caminho do comprovante a outros sites e preserva navegação e formulários locais.
Em `fetch()` com modo `cors`, `no-referrer` mantém o `Origin`; o caso de `Origin: null` se aplica
a formulários e navegação. As respostas do SPA também recusam enquadramento e MIME sniffing.

## Contas de demonstração

| Conta | Papel | E-mail | Senha pública |
| --- | --- | --- | --- |
| Leiloeiro | leiloeiro | leiloeiro@demo.example | leilao-demo-2026 |
| Comprador 1 | licitante | comprador1@demo.example | leilao-demo-2026 |
| Comprador 2 | licitante | comprador2@demo.example | leilao-demo-2026 |

São contas públicas por desenho, com dinheiro simulado. **Não use dados reais.** Qualquer visitante
que as utiliza controla essas identidades, incluindo seus lotes e reservas. Um lance alto válido
de visitante permanece: o seed não desfaz lances. Ele repõe saldo disponível abaixo de R$ 5.000 até
o alvo de R$ 10.000 e recria os papéis de lote que faltarem, por padrão a cada hora.

Com `SEED_DEMO=true`, o startup semeia uma vez, com prazo de 60 segundos, e depois roda a manutenção
a cada `SEED_INTERVALO_S` (padrão 3600). Uma trava consultiva serializa o seed; use conexão direta
ao PostgreSQL, sem pooler em modo transação. Os lances interrompidos são retomados com chaves estáveis.
Erros são registrados e não impedem a API de iniciar. O comando `uv run python -m app.demo` executa
uma rodada manual, mesmo com a flag desligada, e imprime um resumo sem senha.

`GET /api/demo` alimenta os botões de acesso rápido da tela de login e lista somente as contas
conferidas neste processo. `SENHA_DEMO` pode definir uma senha privada antes do primeiro boot; nesse
caso a rota devolve `senha: null` e os botões só preenchem o e-mail. O seed nunca troca a senha de
uma conta existente: divergência de senha ou papel interrompe a rodada antes de movimentar saldo.

## Tempo real (WebSocket)

`/ws` usa o cookie de sessão e exige `Origin` presente na lista `CORS_ORIGINS`. O handshake recusado
responde HTTP 403 (o navegador normalmente informa 1006), inclusive por lotação ou falha de autenticação
no banco. Sem cookie ou com sessão inválida, a conexão é anônima. A primeira mensagem é sempre `ola`.
Cada frame é JSON com `v: 1` e os campos abaixo, sem valores, nomes, e-mails ou pseudônimos:

| Tipo | Campos além de `v` e `tipo` | Destinatários |
| --- | --- | --- |
| `ola` | `autenticado` | a conexão que acabou de entrar |
| `ping` | nenhum | a conexão, após 25 s sem envio |
| `lote_publicado`, `lote_atualizado`, `lote_cancelado`, `lote_encerrado` | `lote_id`, `versao` | todos, inclusive anônimos |
| `carteira_atualizada` | nenhum | somente sessões dos usuários afetados |

O cliente não envia comandos pelo socket. Cada sinal invalida as consultas pertinentes; versões já
conhecidas são descartadas. `ola` refaz as consultas ativas, incluindo uma segunda leitura quando um
GET anterior ainda está em curso. Na troca de conta, dados personalizados e telas são reiniciados;
respostas de mutações da identidade anterior são descartadas.

Depois do `accept`, os fechamentos são 1000 (normal), 1013 (fila cheia), 4001 (logout, sessão inválida
ou prazo de revalidação esgotado) e 1012 (encerramento do processo). Logout descarta os sinais
pendentes daquela sessão; envios têm prazo de 10 segundos. A sessão é revalidada a cada 300 s.

A reconexão espera progressivamente de 1 s a 30 s, com variação aleatória; 4001 reconecta sem espera.
Sessenta segundos sem mensagens também provocam reconexão. Sem WebSocket, a sala consulta a cada
5 s e listas/carteira a cada 15 s. Conectada, a sala mantém uma consulta a cada 60 s; aguardando
liquidação, a cada 3 s. Mudanças de fase agendam consultas pelo relógio do servidor.

Execute **um processo e um worker**. A central é em memória, sem Redis ou comunicação entre processos:
com múltiplos workers, os eventos de um processo não chegam às conexões dos demais.

## Limites conhecidos

- O socket transporta sinais e cada atualização exige GET; a solução atende à escala de demonstração.
- Sessão vencida ou revogada fora do logout pode permanecer conectada até a próxima revalidação,
  normalmente em até 5 minutos. Falhas de banco têm tolerância máxima adicional de 60 s sem validação.
- O limite global padrão é 500 conexões (`WS_MAX_CONEXOES`), com 64 mensagens por fila
  (`WS_TAMANHO_FILA`). Conexões lentas são fechadas; a interface continua por consultas periódicas.
- Na primeira subida, o lote curto encerra cerca de dois minutos depois e gera um comprovante real
  de dinheiro simulado. Há também dois lotes longos ao vivo e um agendado. Reiniciar preserva os lotes
  que ainda satisfazem o catálogo, em vez de duplicá-los.
- Met bloqueado impede buscar ou criar itens ainda não guardados; vitrine, sala, mídia, carteira,
  auditoria e comprovante existentes continuam funcionando.
- As quatro imagens CC0 do Met e seus snapshots estão versionados em `backend/app/demo/dados/`.
  O seed funciona sem acessar a rede.
