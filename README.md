# Casa de Leilões

Casa de leilões online feita para o teste técnico Elite Dev da Verzel. O leiloeiro monta lotes a
partir de obras do acervo aberto do Metropolitan Museum, e os compradores disputam com lances ao
vivo usando uma carteira de dinheiro simulado. O arremate debita o vencedor, credita o leiloeiro e
gera um comprovante público. Cada lote tem uma auditoria pública que detecta adulteração feita direto
no banco de dados.

**Aplicação no ar:** <https://casa-de-leiloes-6kvn.onrender.com>
**Documentação interativa da API:** <https://casa-de-leiloes-6kvn.onrender.com/api/docs>

> O serviço roda no plano gratuito do Render e dorme depois de 15 minutos sem acesso. O primeiro
> acesso depois disso leva cerca de 1 minuto para responder. Os acessos seguintes são imediatos.

## Sumário

1. [Como usar o site](#como-usar-o-site)
2. [Contas de demonstração](#contas-de-demonstração)
3. [Funcionalidades](#funcionalidades)
4. [Tecnologias e arquitetura](#tecnologias-e-arquitetura)
5. [Como executar localmente](#como-executar-localmente)
6. [Banco de dados](#banco-de-dados)
7. [Variáveis de ambiente](#variáveis-de-ambiente)
8. [Testes](#testes)
9. [Deploy](#deploy)
10. [Regras de negócio](#regras-de-negócio)
11. [API](#api)
12. [Tempo real](#tempo-real)
13. [Auditoria e comprovante](#auditoria-e-comprovante)
14. [Comportamentos inesperados e limites conhecidos](#comportamentos-inesperados-e-limites-conhecidos)

## Como usar o site

**Vitrine.** A página inicial lista os lotes ao vivo, agendados e encerrados. A busca filtra pelo
título da obra, e os botões de fase filtram a lista. A vitrine, as salas dos lotes, as auditorias e
os comprovantes abrem sem login.

**Entrar.** Em **Entrar**, os botões de acesso rápido entram com as
[contas de demonstração](#contas-de-demonstração). Para criar uma conta própria, use **Criar conta** e
escolha o papel de comprador ou de leiloeiro.

**Dar lances (comprador).**

1. Em **Carteira**, deposite um valor simulado. As contas de demonstração já têm saldo.
2. Abra um lote ao vivo. A sala mostra o lance atual, o mínimo para o próximo lance, a contagem
   regressiva e o histórico.
3. Digite o valor e confirme. Se outro comprador cobrir o seu lance, a sala atualiza na hora e o
   valor comprometido volta para a sua carteira.
4. Em **Meus arremates**, acompanhe as disputas em andamento e os resultados. Nos lotes que você
   venceu, abra o comprovante, que tem um link público para compartilhar.

Para ver o tempo real funcionando, abra o mesmo lote em duas janelas (uma delas anônima), entre como
comprador 1 numa e comprador 2 na outra e dê lances alternados.

**Criar lotes (leiloeiro).**

1. No **Painel**, clique em **Novo lote** e busque uma obra no acervo do Met, por exemplo "sunflowers".
2. Escolha a obra, defina lance inicial, incremento, início e fim e publique.
3. No **Painel**, acompanhe os seus lotes, os resultados, os comprovantes e o total recebido. Um lote
   ainda sem lance pode ser cancelado ali.

**Auditoria.** Na sala de qualquer lote, **Ver auditoria** confere toda a cadeia de eventos do lote e
mostra se ela está íntegra.

**Tema.** O seletor no cabeçalho alterna entre claro, escuro e o tema do sistema.

## Contas de demonstração

| Conta | Papel | E-mail | Senha |
| --- | --- | --- | --- |
| Leiloeiro | leiloeiro | `leiloeiro@demo.example` | `leilao-demo-2026` |
| Comprador 1 | licitante | `comprador1@demo.example` | `leilao-demo-2026` |
| Comprador 2 | licitante | `comprador2@demo.example` | `leilao-demo-2026` |

A tela de login tem botões de acesso rápido que preenchem essas credenciais. Também é possível criar
uma conta nova em **Criar conta**, escolhendo o papel de leiloeiro ou de comprador.

As contas de demonstração são públicas de propósito e usam dinheiro simulado. Qualquer visitante que
entrar nelas controla essas identidades, inclusive os lotes e as reservas do seed. Não use dados
reais.

O seed mantém a demonstração viva sozinho. Ele roda quando o servidor sobe e depois a cada hora:

- garante um lote ao vivo com lances dos dois compradores. Quando falta menos de 1 dia para o lote
  atual terminar, cria outro com 14 dias de duração, e o anterior segue até o arremate normal
- garante um lote agendado. Quando ele está a menos de 1 hora de abrir, cria o próximo
- repõe o saldo disponível das contas de demonstração quando ele fica abaixo de R$ 5.000,00, até
  R$ 10.000,00

Por isso a aplicação continua com lotes em disputa mesmo semanas depois do deploy.

## Funcionalidades

**Comprador (licitante)**

- Vitrine com busca por título e filtro por fase (ao vivo, agendado, encerrado).
- Sala do lote com contagem regressiva pelo relógio do servidor, lance mínimo, histórico de lances
  com pseudônimos e posição na disputa.
- Carteira com depósito simulado, saldo total, valor comprometido e disponível.
- Lances atualizados em tempo real por WebSocket, com aviso de prorrogação nos últimos 2 minutos.
- **Meus arremates**, com as disputas em andamento, os resultados e o comprovante de cada lote
  vencido.

**Leiloeiro**

- Busca no acervo do Met, só com obras em domínio público e com imagem.
- Publicação de lote com lance inicial, incremento, início e fim.
- Painel com os próprios lotes, resultado de cada um, comprovantes e total recebido.
- Cancelamento de lote que ainda não recebeu lance.

**Público, sem login**

- Vitrine e salas dos lotes.
- Auditoria de cada lote, com o veredito de integridade da cadeia de eventos.
- Comprovante de arremate pelo link público.

**Opcionais do enunciado**

| Opcional | Situação |
| --- | --- |
| Busca e filtro de lotes | Feito: busca por título e filtro por fase na vitrine. |
| Cancelamento com estorno automático | Parcial, por decisão: só se cancela lote sem lance, então não há valor a estornar. Ver [Regras de negócio](#regras-de-negócio). |
| Docker Compose | Feito: banco, API e front com um comando. |
| Testes automatizados | Feito: 332 testes no back-end, incluindo concorrência contra PostgreSQL real, e 243 no front-end. |
| Dark mode | Feito: tema claro, escuro ou do sistema, escolhido no cabeçalho. |

## Tecnologias e arquitetura

| Camada | Tecnologia |
| --- | --- |
| Back-end | Python 3.12, FastAPI, SQLAlchemy 2 assíncrono, psycopg 3, Alembic, Pydantic 2, Argon2 |
| Front-end | React 19, Vite, TypeScript estrito, Tailwind CSS 4, React Router, TanStack Query |
| Banco de dados | PostgreSQL 17 |
| Tempo real | WebSocket nativo do FastAPI no mesmo processo da API |
| Infraestrutura | Docker Compose local, Render (aplicação) e Neon (PostgreSQL) em produção |

```
backend/
  app/api/          rotas finas, uma por recurso
  app/schemas/      contratos Pydantic (entrada com extra="forbid")
  app/models/       tabelas SQLAlchemy
  app/services/     regras de negócio
    regras.py, cadeia.py, verificacao.py   núcleo puro, sem I/O
    lances.py, liquidacao.py, encerramento.py, carteira.py, ...   I/O sobre o núcleo
  app/db/           transação com retentativa e níveis de isolamento
  app/demo/         seed de demonstração, com snapshots e imagens locais
  app/web/          serve o build do front pela própria API em produção
  alembic/          migration escrita à mão, conferida contra os modelos
  tests/            pytest, com marcador `pg` para os testes com PostgreSQL real
frontend/
  src/api/          cliente HTTP, tipos espelhando os schemas, consultas e sessão
  src/lib/          dinheiro, relógio do servidor, erros, datas, tema
  src/tempoReal/    conexão WebSocket com reconexão e despacho de invalidações
  src/components/   componentes próprios (calendário, dicas, seletor de tema)
  src/pages/        telas
```

### Decisões principais

**Dinheiro em centavos inteiros.** Todo valor monetário é `int` no Python e `BIGINT` no banco, nunca
`float`. Ponto flutuante não representa 0,10 com exatidão, e somar lances e saldos em `float` acumula
erro. O front faz o parse de reais como texto e também trabalha em centavos. Os valores ficam abaixo
de 2^53, o maior inteiro que o JavaScript representa com exatidão.

**Monólito modular.** API, WebSocket, worker de encerramento e seed rodam num único processo. O
problema central é consistência sob concorrência, e um único processo com o PostgreSQL como fonte da
verdade resolve isso sem fila, sem Redis e sem coordenação distribuída. A separação fica no código,
entre o núcleo puro e a camada de I/O.

**Concorrência por travas no banco.** Cada lance roda numa transação que trava o lote e depois as
carteiras envolvidas, sempre nessa ordem e com as carteiras em ordem crescente de id, o que evita
deadlock entre lances simultâneos. O instante do lance é lido com `clock_timestamp()` depois das
travas, então a regra de prorrogação usa a ordem real de chegada. Deadlock ou espera de trava acima
de 3 segundos repetem a transação inteira até 3 vezes.

**Razão contábil.** O saldo de cada carteira é a soma dos seus lançamentos (depósito, débito de
arremate, crédito de venda). O valor comprometido é a reserva do líder de cada lote, e existe no
máximo uma reserva por lote. Ao ser superado, o comprador perde a reserva e o valor volta ao
disponível na mesma transação.

**Idempotência.** Lance e depósito exigem o cabeçalho `Idempotency-Key`. Repetir a mesma chave com o
mesmo corpo devolve a resposta original, com `Idempotency-Replayed: true`, sem gravar de novo. Isso
protege contra clique duplo e contra repetição depois de falha de rede.

**Sessão por cookie.** A senha é guardada com Argon2id. O login gera um token opaco aleatório,
guardado no banco só como hash, e entregue num cookie `HttpOnly`, `SameSite=Lax` e `Secure` em
produção. Toda escrita exige um `Origin` permitido, o que bloqueia CSRF.

**Front e API na mesma origem.** Em produção, a própria API serve o build do React. Assim o cookie
de sessão é de primeira parte e o WebSocket usa o mesmo endereço, sem depender de cookie entre
domínios.

## Como executar localmente

### Com Docker Compose (recomendado)

Requisito: Docker com o plugin Compose.

```sh
git clone https://github.com/manoelbcruz/verzel-dev.git
cd verzel-dev
docker compose up --build
```

Depois que os três serviços subirem:

- aplicação: <http://localhost:8080>
- documentação da API: <http://localhost:8080/api/docs>
- health check: <http://localhost:8080/api/health>

O Compose sobe o PostgreSQL 17, a API (que roda as migrations antes de iniciar) e o front servido
por nginx, que encaminha `/api/` e `/ws` para a API. O seed de demonstração roda no primeiro boot com
as mesmas contas da tabela acima. As chaves e a senha do banco do Compose são públicas e servem só
para desenvolvimento local.

Para parar, use `docker compose down`. Os dados ficam no volume `pgdata`. Para começar do zero, use
`docker compose down -v`, que apaga o volume.

### Sem Docker para a aplicação

Requisitos: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 24 e npm. O PostgreSQL pode vir do
próprio Compose.

1. Suba só o banco, na raiz do repositório:

   ```sh
   docker compose up -d db
   ```

   A porta 5432 fica publicada apenas em `127.0.0.1`. Se ela já estiver ocupada, use
   `DB_PORT=5433 docker compose up -d db` e ajuste a porta na `DATABASE_URL`.

2. Em outro terminal, configure e suba a API:

   ```sh
   cd backend
   cp .env.example .env
   uv sync --locked
   export CHAVE_INTEGRIDADE="$(uv run python -c 'import secrets; print(secrets.token_hex(32))')"
   export CHAVE_PRIVACIDADE="$(uv run python -c 'import secrets; print(secrets.token_hex(32))')"
   export CORS_ORIGINS=http://localhost:5173
   uv run alembic upgrade head
   uv run uvicorn app.main:app --reload
   ```

   As chaves geradas assim mudam a cada terminal. Para manter os dados entre execuções, grave as duas
   no `backend/.env`. Trocar as chaves depois de criar lotes faz a auditoria acusar adulteração (ver
   [Variáveis de ambiente](#variáveis-de-ambiente)).

3. Em outro terminal, suba o front:

   ```sh
   cd frontend
   npm ci
   npm run dev
   ```

   Acesse <http://localhost:5173>. O Vite encaminha `/api` e `/ws` para a API na porta 8000.

### Chamando a API pela linha de comando

Toda escrita exige um `Origin` permitido, e lance e depósito exigem `Idempotency-Key` (8 a 128
caracteres entre letras ASCII, números, `_` e `-`). Exemplo contra o Compose:

```sh
curl -c cookies.txt -X POST http://localhost:8080/api/auth/login \
  -H 'Origin: http://localhost:8080' -H 'Content-Type: application/json' \
  -d '{"email":"comprador1@demo.example","senha":"leilao-demo-2026"}'

curl -b cookies.txt -X POST http://localhost:8080/api/carteira/depositos \
  -H 'Origin: http://localhost:8080' -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: deposito-0001' -d '{"valor_centavos":100000}'
```

## Banco de dados

O projeto usa PostgreSQL 17. A aplicação só precisa de uma `DATABASE_URL` que aponte para um banco
vazio ou já migrado.

**Configuração.** A `DATABASE_URL` aceita os formatos `postgres://`, `postgresql://` e
`postgresql+psycopg://`, então a URL entregue por provedores gerenciados (Neon, Render, Supabase)
pode ser colada como vem. Parâmetros como `?sslmode=require` são mantidos.

**Migrations.** O schema é criado pelo Alembic. A imagem Docker roda `alembic upgrade head` antes de
iniciar a API. Fora do Docker, rode o comando manualmente, como no passo 2 acima. A migration
`0001_inicial` foi escrita à mão, e um teste confere se ela bate com os modelos.

**Seed.** Com `SEED_DEMO=true`, o seed roda no startup e a cada `SEED_INTERVALO_S` segundos (padrão
3600). Para rodar uma única vez, sem depender da flag:

```sh
cd backend
uv run python -m app.demo
```

O seed usa uma trava consultiva do PostgreSQL para que duas rodadas não se sobreponham. Por isso a
conexão precisa ser direta. Pooler em modo transação, como o endereço `-pooler` do Neon ou o
PgBouncer nesse modo, não serve.

**Acesso direto ao banco do Compose:**

```sh
docker compose exec db psql -U leilao -d leilao
```

**Banco de testes.** A suíte usa um banco separado, cujo nome precisa terminar em `_test`, porque os
testes apagam as tabelas antes de cada caso. Veja [Testes](#testes).

## Variáveis de ambiente

| Variável | Obrigatória | Padrão | Para que serve |
| --- | --- | --- | --- |
| `DATABASE_URL` | sim | banco local `leilao` | conexão com o PostgreSQL |
| `CHAVE_INTEGRIDADE` | sim | nenhum | chave HMAC da cadeia de auditoria, em hexadecimal, com 32 bytes ou mais |
| `CHAVE_PRIVACIDADE` | sim | nenhum | chave HMAC dos pseudônimos dos licitantes, distinta da anterior |
| `CORS_ORIGINS` | sim | `http://localhost:5173` | origens aceitas, separadas por vírgula, sem barra no final |
| `ENVIRONMENT` | não | `development` | `production` liga o cookie `Secure` e recusa as chaves de desenvolvimento |
| `SEED_DEMO` | não | `false` | liga o seed de demonstração |
| `SEED_INTERVALO_S` | não | `3600` | intervalo entre rodadas do seed |
| `SENHA_DEMO` | não | `leilao-demo-2026` | senha das contas de demonstração no primeiro boot |
| `FRONTEND_DIST` | não | vazio | pasta do build do front para a API servir (a imagem de produção define) |
| `PORT` | não | `8000` | porta da API na imagem Docker |
| `SESSAO_DIAS` | não | `7` | duração da sessão |
| `DB_POOL_SIZE` e `DB_MAX_OVERFLOW` | não | `5` e `10` | tamanho do pool de conexões |
| `WS_MAX_CONEXOES` e `WS_TAMANHO_FILA` | não | `500` e `64` | limites do WebSocket |

As duas chaves ficam fora do banco de propósito. Quem altera o banco sem conhecê-las não consegue
recalcular os HMAC da cadeia. Elas precisam ser guardadas assim que os primeiros dados forem criados.
Trocar `CHAVE_INTEGRIDADE` faz todos os lotes existentes aparecerem como adulterados, e trocar
`CHAVE_PRIVACIDADE` muda os pseudônimos. Em produção, a API se recusa a subir com as chaves públicas
do Compose ou com duas chaves iguais.

Para gerar uma chave: `openssl rand -hex 32`.

## Testes

**Back-end**, na pasta `backend/`:

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Sem banco configurado, a suíte roda o núcleo puro, as rotas com HTTP simulado e o WebSocket em
processo, e pula os testes marcados `pg`. Para rodar tudo, incluindo concorrência, liquidação,
adulteração, migration, seed e WebSocket com uvicorn real:

```sh
docker compose up -d db   # na raiz
TEST_DATABASE_URL=postgresql+psycopg://leilao:leilao@localhost:5432/leilao_test uv run pytest
```

Os testes criam o banco de teste se ele não existir e esvaziam as tabelas antes de cada caso. Nunca
aponte `TEST_DATABASE_URL` para um banco com dados reais. O nome precisa terminar em `_test`, e a
suíte se recusa a rodar se não terminar.

O que a suíte cobre, entre outros pontos:

- lances simultâneos no mesmo lote e o mesmo saldo disputado em dois lotes ao mesmo tempo
- lance disputando com o encerramento e com o cancelamento do lote
- prorrogação nos últimos 2 minutos, nos limites de tempo da regra
- idempotência com dez depósitos simultâneos na mesma chave e lance repetido em paralelo
- adulteração feita por `UPDATE`, `INSERT` e `DELETE` direto no banco, detectada pela auditoria
- liquidação bloqueada quando a carteira diverge do razão
- WebSocket com origem recusada, sinal privado só para o dono, logout e revalidação

**Front-end**, na pasta `frontend/`:

```sh
npm run typecheck
npm test
npm run build
```

O Vitest cobre o parse de dinheiro, o relógio do servidor, a reconexão do WebSocket, a troca de
identidade com respostas pendentes, a idempotência dos envios e os fluxos das telas.

## Deploy

A aplicação está no Render, plano gratuito, região Virginia, com o banco no Neon (PostgreSQL 17,
plano gratuito, mesma região da AWS). Banco e aplicação na mesma região mantêm baixa a latência de
cada consulta, e um lance faz várias consultas seguidas.

A raiz do repositório tem os dois arquivos de deploy:

- `Dockerfile`, em dois estágios. O primeiro gera o build do front com Node 24. O segundo instala a
  API com Python 3.12, copia o build para `/app/static` e roda as migrations antes do uvicorn. Sobe
  com um único worker, porque a central do WebSocket fica em memória. A imagem não leva testes nem
  arquivos `.env`.
- `render.yaml`, um Blueprint do Render com o serviço web, o health check em `/api/health` e as
  variáveis. As variáveis secretas ficam marcadas para preenchimento no painel.

Para reproduzir o deploy:

1. Crie um projeto no Neon com PostgreSQL 17 e copie a connection string **sem** pooling (o endereço
   não pode ter `-pooler`).
2. No Render, crie um Blueprint apontando para o repositório. Ele lê o `render.yaml`.
3. Preencha `DATABASE_URL` com a string do Neon, `CHAVE_INTEGRIDADE` e `CHAVE_PRIVACIDADE` com duas
   saídas diferentes de `openssl rand -hex 32` e `CORS_ORIGINS` com o endereço público do serviço,
   com `https://` e sem barra no final.
4. Faça o deploy. A migration e o seed rodam sozinhos no primeiro boot.

Para testar a imagem de produção localmente, com o banco do Compose em pé:

```sh
docker build -t casa-de-leiloes .
docker compose exec db psql -U leilao -d leilao -c "CREATE DATABASE leilao_prod"
docker run --rm --network verzel-dev_default -p 8090:10000 -e PORT=10000 \
  -e ENVIRONMENT=production -e SEED_DEMO=true -e CORS_ORIGINS=http://localhost:8090 \
  -e DATABASE_URL=postgresql://leilao:leilao@db:5432/leilao_prod \
  -e CHAVE_INTEGRIDADE=$(openssl rand -hex 32) -e CHAVE_PRIVACIDADE=$(openssl rand -hex 32) \
  casa-de-leiloes
```

O nome da rede segue o nome da pasta do clone (`<pasta>_default`).

## Regras de negócio

- **Fases.** Um lote é agendado antes do início, ao vivo entre o início e o fim, e encerrado depois
  do fim. Lance só é aceito com o lote ao vivo.
- **Valor dos lances.** O primeiro lance precisa ser maior ou igual ao lance inicial. Os seguintes
  precisam ser maiores ou iguais ao lance atual mais o incremento. O "valor mínimo" do painel do
  leiloeiro é o lance inicial.
- **Quem pode dar lance.** O líder não cobre o próprio lance, e o leiloeiro não dá lance.
- **Saldo.** O lance precisa caber no saldo disponível, que é o saldo total menos o comprometido. O
  valor do lance fica reservado enquanto o comprador lidera. Ao ser superado, a reserva volta para o
  disponível na hora.
- **Prorrogação (anti-sniping).** Um lance nos últimos 2 minutos muda o fim para o instante do lance
  mais 2 minutos: `fim_novo = max(fim_atual, instante_do_lance + 120 s)`. O fim nunca recua. Um
  lance com exatos 120 segundos restantes deixa o fim igual.
- **Encerramento e liquidação.** Um worker verifica a cada segundo os lotes vencidos. A liquidação
  debita o vencedor, credita o leiloeiro, libera a reserva e gera o comprovante, tudo numa transação.
  Lote sem lance fecha sem vencedor. Abrir a sala de um lote vencido também dispara o encerramento.
- **Cancelamento.** O leiloeiro só cancela lote sem lance, e lote cancelado sai da vitrine. Como não
  há lance, não há reserva a devolver. Cancelar lote com lances exigiria decidir o que fazer com a
  disputa em andamento, e essa regra não está no enunciado. Por isso o estorno automático ficou fora.

## API

A documentação completa, com os schemas, fica em `/api/docs`. As rotas principais:

| Método e rota | Acesso | O que faz |
| --- | --- | --- |
| `POST /api/auth/cadastro` | público | cria conta de leiloeiro ou licitante |
| `POST /api/auth/login` e `POST /api/auth/logout` | público e sessão | entra e sai |
| `GET /api/auth/me` | sessão | dados da conta logada |
| `GET /api/demo` | público | contas do acesso rápido |
| `GET /api/lotes?q=` | público | vitrine agrupada por fase, com busca por título |
| `GET /api/lotes/{id}` | público | detalhe do lote e histórico de lances |
| `POST /api/lotes/{id}/lances` | licitante | dá um lance (exige `Idempotency-Key`) |
| `GET /api/lotes/{id}/auditoria` | público | verifica a cadeia de eventos do lote |
| `GET /api/carteira` e `POST /api/carteira/depositos` | licitante | carteira e depósito (exige `Idempotency-Key`) |
| `GET /api/me/participacoes` | licitante | disputas e arremates |
| `GET /api/comprovantes/{codigo}` | público | comprovante de arremate |
| `GET /api/leiloeiro/itens?q=` e `GET /api/leiloeiro/itens/{id}` | leiloeiro | busca no acervo do Met |
| `GET` e `POST /api/leiloeiro/lotes` | leiloeiro | painel e publicação de lote |
| `POST /api/leiloeiro/lotes/{id}/cancelar` | leiloeiro | cancela lote sem lance |
| `GET /api/midias/{sha256}` | público | imagem guardada do lote |
| `GET /ws` | público, com sessão opcional | sinais de tempo real |

Todo erro segue o mesmo formato, com códigos estáveis que o front traduz em mensagens:

```json
{"erro": {"codigo": "abaixo_do_minimo", "mensagem": "O lance está abaixo do mínimo.", "detalhes": {"minimo_centavos": 180000}}}
```

Respostas públicas não expõem nome, e-mail nem id interno. O licitante aparece no histórico por um
pseudônimo de 26 caracteres, diferente em cada lote.

## Tempo real

O endpoint `/ws` envia apenas sinais. A mensagem diz o que mudou, e o front refaz a leitura pela API.
Assim o estado exibido sempre vem do banco, e um sinal perdido não deixa a tela inconsistente.

| Tipo | Campos além de `v` e `tipo` | Quem recebe |
| --- | --- | --- |
| `ola` | `autenticado` | a conexão que acabou de entrar |
| `ping` | nenhum | a conexão, depois de 25 s sem envio |
| `lote_publicado`, `lote_atualizado`, `lote_cancelado`, `lote_encerrado` | `lote_id`, `versao` | todas as conexões, inclusive anônimas |
| `carteira_atualizada` | nenhum | só as conexões do usuário afetado |

O handshake confere o `Origin` antes de tocar no banco e identifica o usuário pelo cookie `sessao`.
Sem sessão, a conexão é anônima e recebe só os sinais públicos. O logout fecha as conexões daquela
sessão com o código 4001, e as sessões abertas são revalidadas a cada 5 minutos.

O front reconecta com espera progressiva de 1 a 30 segundos. Sem WebSocket, a sala do lote consulta
a API a cada 5 segundos e as listas a cada 15, então a aplicação continua utilizável com a conexão
instável.

## Auditoria e comprovante

Cada lote tem uma cadeia de eventos (publicação, lances, cancelamento, encerramento, liquidação).
Cada evento é autenticado com HMAC-SHA-256 sobre o seu conteúdo canônico e o MAC do evento anterior,
e a cabeça da cadeia tem um HMAC próprio, com domínio de separação distinto. A chave fica fora do
banco, então quem altera o banco não consegue recalcular os MAC.

A verificação compara a cadeia com as tabelas que o usuário vê: lances, lote, reserva, liquidação e
lançamentos da carteira. Ela detecta alteração, inserção e remoção parcial de registros, e também a
"lavagem", em que o banco é alterado de forma coerente em várias tabelas ao mesmo tempo. Toda escrita
sobre um lote roda a verificação completa antes. Se a cadeia não confere, o lance é recusado com
`409 lote_adulterado` e nada é gravado. A liquidação também só move dinheiro se as carteiras do
vencedor e do leiloeiro baterem com o razão.

O comprovante de arremate tem um código público. A página do comprovante mostra obra, valor,
data e o pseudônimo do vencedor, e aponta para a auditoria do lote.

## Comportamentos inesperados e limites conhecidos

**Hospedagem**

- O serviço gratuito dorme depois de 15 minutos sem acesso, e o primeiro acesso depois disso leva
  cerca de 1 minuto. Enquanto o serviço dorme, o worker também para. Um lote que vencer nesse
  intervalo só é liquidado quando o serviço acorda, e a sala mostra "Encerrando…" e o painel mostra
  "Apurando resultado" por alguns segundos.
- A aplicação roda com um único processo. A central do WebSocket fica em memória, e mais de um
  worker dividiria as conexões entre centrais que não se falam. Escalar horizontalmente exigiria um
  canal compartilhado, como Redis Pub/Sub ou `LISTEN/NOTIFY` do PostgreSQL.

**Contas de demonstração**

- As contas são públicas e compartilhadas. Se outro avaliador estiver usando a mesma conta, os lances
  e o saldo dele aparecem para você também.
- O seed não desfaz lances de visitantes. Um lance alto feito por alguém continua valendo, e o seed
  só cria um lote novo quando o atual estiver perto do fim.
- No primeiro boot de um banco vazio, o seed cria um lote curto que encerra cerca de 2 minutos depois
  e gera um comprovante real, para que a vitrine já tenha um lote encerrado com vencedor.

**Acervo do Met**

- A busca do Met devolve todos os ids de uma vez, e a paginação fatia essa lista antes de filtrar as
  obras elegíveis (domínio público e com imagem). Por isso uma página pode vir com menos de 20 obras,
  ou até vazia, mesmo havendo próxima página.
- Com o Met fora do ar, a busca usa o cache quando existe e informa a origem. Criar lote de uma obra
  que não está em cache fica indisponível. Vitrine, salas, imagens, carteira, auditoria e
  comprovantes continuam funcionando, porque o snapshot e a imagem de cada lote ficam no banco.

**Auditoria**

- Restaurar um estado antigo inteiro do banco (eventos, lote, reserva e cabeça da cadeia, todos de
  um mesmo momento passado) não é detectado, porque esse estado foi autenticado de verdade naquele
  momento. Detectar isso exigiria uma âncora externa, como publicar a cabeça de cada cadeia fora do
  banco.
- A auditoria cobre o lote e o dinheiro que ele moveu. Depósitos, usuários e papéis ficam fora da
  cadeia. Um lote pode aparecer como íntegro na auditoria e ter a liquidação bloqueada por
  divergência na carteira de alguém.
- Um lote bloqueado por cadeia inválida ou carteira divergente aparece como encerrado sem resultado
  e mantém a reserva do líder até intervenção manual. O log registra o motivo.
- A verificação exige que os instantes dos eventos de um lote estejam em ordem. Se o relógio do
  servidor do banco voltar no tempo entre dois eventos, a auditoria pode acusar adulteração sem ter
  havido uma.

**Sessão e tempo real**

- Uma sessão revogada por outro caminho que não o logout pode continuar com o WebSocket aberto por
  até 5 minutos, até a próxima revalidação. Os dados continuam protegidos, porque os sinais não
  levam dados e toda leitura pela API confere a sessão.
- Quando o navegador recusa o handshake do WebSocket (origem não permitida, limite de conexões), ele
  costuma reportar o código 1006 em vez do 403 real.
- O limite padrão é de 500 conexões simultâneas. Conexões lentas demais são fechadas, e a interface
  segue pelas consultas periódicas.
- Repetir um lance com a mesma `Idempotency-Key` devolve o sucesso original, mesmo que o lance já
  tenha sido superado ou o lote encerrado. Um lance recusado não consome a chave, então repeti-lo
  reavalia as regras.
