"""Schema inicial do domínio; constraints nomeadas e sem ENUMs do PostgreSQL."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001_inicial"
down_revision = None
branch_labels = None
depends_on = None


def coluna(nome, tipo, *, nulo=False, padrao=None):
    return sa.Column(nome, tipo, nullable=nulo, server_default=padrao)


def identidade():
    return sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False)


def data(nome, *, nulo=False, agora=False):
    return coluna(
        nome, sa.DateTime(timezone=True), nulo=nulo, padrao=sa.text("now()") if agora else None
    )


def pk(tabela, campo="id"):
    return sa.PrimaryKeyConstraint(campo, name=op.f(f"pk_{tabela}"))


def fk(tabela, campo, destino):
    return sa.ForeignKeyConstraint(
        [campo], [destino], name=op.f(f"fk_{tabela}_{campo}_{destino.split('.')[0]}")
    )


def ck(tabela, nome, expressao):
    return sa.CheckConstraint(expressao, name=op.f(f"ck_{tabela}_{nome}"))


def uq(tabela, *campos, nome=None):
    return sa.UniqueConstraint(*campos, name=op.f(nome or f"uq_{tabela}_{campos[0]}"))


def indice(tabela, *campos, nome=None):
    op.create_index(op.f(nome or f"ix_{tabela}_{campos[0]}"), tabela, list(campos))


def upgrade():
    op.create_table(
        "usuarios",
        identidade(),
        coluna("nome", sa.Text()),
        coluna("email", sa.Text()),
        coluna("senha_hash", sa.Text()),
        coluna("papel", sa.Text()),
        data("criado_em", agora=True),
        pk("usuarios"),
        uq("usuarios", "email"),
        ck("usuarios", "papel_valido", "papel IN ('leiloeiro','licitante')"),
    )
    op.create_table(
        "sessoes",
        identidade(),
        coluna("usuario_id", sa.BigInteger()),
        coluna("token_hash", sa.LargeBinary()),
        data("criada_em", agora=True),
        data("expira_em"),
        data("revogada_em", nulo=True),
        pk("sessoes"),
        fk("sessoes", "usuario_id", "usuarios.id"),
        uq("sessoes", "token_hash"),
        ck("sessoes", "token_hash_32", "octet_length(token_hash) = 32"),
    )
    indice("sessoes", "usuario_id")
    op.create_table(
        "carteiras",
        coluna("usuario_id", sa.BigInteger()),
        coluna("saldo_centavos", sa.BigInteger(), padrao=sa.text("0")),
        data("atualizada_em", agora=True),
        pk("carteiras", "usuario_id"),
        fk("carteiras", "usuario_id", "usuarios.id"),
        ck("carteiras", "saldo_nao_negativo", "saldo_centavos >= 0"),
        ck("carteiras", "saldo_seguro_js", "9007199254740991 >= saldo_centavos"),
    )
    op.create_table(
        "midias",
        identidade(),
        coluna("sha256", sa.Text()),
        coluna("content_type", sa.Text()),
        coluna("tamanho_bytes", sa.Integer()),
        coluna("dados", sa.LargeBinary()),
        coluna("origem_url", sa.Text()),
        data("criado_em", agora=True),
        pk("midias"),
        uq("midias", "sha256"),
        ck("midias", "sha256_hex", "sha256 ~ '^[0-9a-f]{64}$'"),
        ck("midias", "tipo_permitido", "content_type IN ('image/jpeg','image/png','image/webp')"),
        ck("midias", "tamanho_valido", "tamanho_bytes BETWEEN 1 AND 5000000"),
    )
    indice("midias", "origem_url")
    op.create_table(
        "lotes",
        identidade(),
        coluna("public_id", sa.Uuid()),
        coluna("leiloeiro_id", sa.BigInteger()),
        coluna("status", sa.Text()),
        coluna("item_fonte", sa.Text()),
        coluna("item_id_externo", sa.Text()),
        coluna("titulo", sa.Text()),
        coluna("atributos", postgresql.JSONB()),
        coluna("midia_id", sa.BigInteger()),
        coluna("lance_inicial_centavos", sa.BigInteger()),
        coluna("incremento_centavos", sa.BigInteger()),
        data("inicio_em"),
        data("fim_original_em"),
        data("fim_em"),
        coluna("lance_atual_centavos", sa.BigInteger(), nulo=True),
        coluna("lider_id", sa.BigInteger(), nulo=True),
        coluna("total_lances", sa.Integer(), padrao=sa.text("0")),
        coluna("cabeca_seq", sa.Integer()),
        coluna("cabeca_assinatura", sa.LargeBinary()),
        data("criado_em", agora=True),
        pk("lotes"),
        uq("lotes", "public_id"),
        fk("lotes", "leiloeiro_id", "usuarios.id"),
        fk("lotes", "lider_id", "usuarios.id"),
        fk("lotes", "midia_id", "midias.id"),
        ck("lotes", "status_valido", "status IN ('publicado','cancelado','encerrado')"),
        ck("lotes", "lance_inicial_positivo", "lance_inicial_centavos > 0"),
        ck("lotes", "incremento_positivo", "incremento_centavos > 0"),
        ck("lotes", "fim_depois_do_inicio", "fim_original_em > inicio_em"),
        ck("lotes", "fim_nao_recua", "fim_em >= fim_original_em"),
        ck(
            "lotes",
            "projecao_coerente",
            "((total_lances = 0) = (lider_id IS NULL)) AND "
            "((lider_id IS NULL) = (lance_atual_centavos IS NULL))",
        ),
        ck("lotes", "cabeca_seq_positiva", "cabeca_seq > 0"),
        ck("lotes", "cabeca_assinatura_32", "octet_length(cabeca_assinatura) = 32"),
    )
    indice("lotes", "status", "fim_em", nome="ix_lotes_status_fim_em")
    indice("lotes", "leiloeiro_id")
    op.create_table(
        "eventos_lote",
        identidade(),
        coluna("lote_id", sa.BigInteger()),
        coluna("seq", sa.Integer()),
        coluna("tipo", sa.Text()),
        data("instante"),
        coluna("licitante_id", sa.BigInteger(), nulo=True),
        coluna("pseudonimo", sa.Text(), nulo=True),
        coluna("valor_centavos", sa.BigInteger(), nulo=True),
        data("fim_anterior", nulo=True),
        data("fim_novo", nulo=True),
        coluna("mac", sa.LargeBinary()),
        pk("eventos_lote"),
        fk("eventos_lote", "lote_id", "lotes.id"),
        fk("eventos_lote", "licitante_id", "usuarios.id"),
        uq("eventos_lote", "lote_id", "seq", nome="uq_eventos_lote_lote_id_seq"),
        ck("eventos_lote", "seq_positiva", "seq > 0"),
        ck(
            "eventos_lote",
            "tipo_valido",
            "tipo IN ('publicacao','lance','cancelamento','encerramento')",
        ),
        ck("eventos_lote", "mac_32", "octet_length(mac) = 32"),
        ck(
            "eventos_lote",
            "campos_de_lance",
            "(tipo = 'lance' AND licitante_id IS NOT NULL AND pseudonimo IS NOT NULL "
            "AND valor_centavos IS NOT NULL AND fim_anterior IS NOT NULL "
            "AND fim_novo IS NOT NULL AND valor_centavos > 0 AND fim_novo >= fim_anterior) "
            "OR (tipo <> 'lance' AND licitante_id IS NULL AND pseudonimo IS NULL "
            "AND valor_centavos IS NULL AND fim_anterior IS NULL AND fim_novo IS NULL)",
        ),
    )
    indice("eventos_lote", "licitante_id")
    op.create_table(
        "reservas",
        coluna("lote_id", sa.BigInteger()),
        coluna("usuario_id", sa.BigInteger()),
        coluna("valor_centavos", sa.BigInteger()),
        data("atualizada_em", agora=True),
        pk("reservas", "lote_id"),
        fk("reservas", "lote_id", "lotes.id"),
        fk("reservas", "usuario_id", "carteiras.usuario_id"),
        ck("reservas", "valor_positivo", "valor_centavos > 0"),
    )
    indice("reservas", "usuario_id")
    op.create_table(
        "liquidacoes",
        identidade(),
        coluna("lote_id", sa.BigInteger()),
        coluna("resultado", sa.Text()),
        coluna("vencedor_id", sa.BigInteger(), nulo=True),
        coluna("vencedor_pseudonimo", sa.Text(), nulo=True),
        coluna("valor_centavos", sa.BigInteger(), nulo=True),
        coluna("comprovante_codigo", sa.Text(), nulo=True),
        pk("liquidacoes"),
        fk("liquidacoes", "lote_id", "lotes.id"),
        fk("liquidacoes", "vencedor_id", "usuarios.id"),
        uq("liquidacoes", "lote_id"),
        uq("liquidacoes", "comprovante_codigo"),
        ck("liquidacoes", "resultado_valido", "resultado IN ('arrematado','sem_lances')"),
        ck(
            "liquidacoes",
            "campos_por_resultado",
            "(resultado = 'arrematado' AND vencedor_id IS NOT NULL "
            "AND vencedor_pseudonimo IS NOT NULL AND valor_centavos IS NOT NULL "
            "AND comprovante_codigo IS NOT NULL AND valor_centavos > 0) OR "
            "(resultado = 'sem_lances' AND vencedor_id IS NULL AND vencedor_pseudonimo IS NULL "
            "AND valor_centavos IS NULL AND comprovante_codigo IS NULL)",
        ),
    )
    op.create_table(
        "lancamentos",
        identidade(),
        coluna("usuario_id", sa.BigInteger()),
        coluna("tipo", sa.Text()),
        coluna("valor_centavos", sa.BigInteger()),
        coluna("liquidacao_id", sa.BigInteger(), nulo=True),
        data("criado_em", agora=True),
        pk("lancamentos"),
        fk("lancamentos", "usuario_id", "carteiras.usuario_id"),
        fk("lancamentos", "liquidacao_id", "liquidacoes.id"),
        uq("lancamentos", "liquidacao_id", "tipo", nome="uq_lancamentos_liquidacao_id_tipo"),
        ck(
            "lancamentos",
            "tipo_valido",
            "tipo IN ('deposito','arremate_debito','arremate_credito')",
        ),
        ck(
            "lancamentos",
            "sinal_por_tipo",
            "(tipo = 'arremate_debito' AND valor_centavos < 0) OR "
            "(tipo IN ('deposito','arremate_credito') AND valor_centavos > 0)",
        ),
        ck(
            "lancamentos",
            "liquidacao_por_tipo",
            "(tipo = 'deposito' AND liquidacao_id IS NULL) OR "
            "(tipo IN ('arremate_debito','arremate_credito') AND liquidacao_id IS NOT NULL)",
        ),
    )
    indice("lancamentos", "usuario_id")
    op.create_table(
        "chaves_idempotencia",
        identidade(),
        coluna("usuario_id", sa.BigInteger()),
        coluna("operacao", sa.Text()),
        coluna("chave", sa.Text()),
        coluna("impressao", sa.Text()),
        coluna("status_http", sa.Integer(), nulo=True),
        coluna("resposta", postgresql.JSONB(none_as_null=True), nulo=True),
        data("criada_em", agora=True),
        pk("chaves_idempotencia"),
        fk("chaves_idempotencia", "usuario_id", "usuarios.id"),
        ck("chaves_idempotencia", "operacao_valida", "operacao IN ('lance','deposito')"),
        uq(
            "chaves_idempotencia",
            "usuario_id",
            "operacao",
            "chave",
            nome="uq_chaves_idempotencia_usuario_operacao_chave",
        ),
    )
    op.create_table(
        "cache_met",
        coluna("chave", sa.Text()),
        coluna("dados", postgresql.JSONB()),
        data("obtido_em"),
        pk("cache_met", "chave"),
    )


def downgrade():
    for tabela in (
        "cache_met",
        "chaves_idempotencia",
        "lancamentos",
        "liquidacoes",
        "reservas",
        "eventos_lote",
        "lotes",
        "midias",
        "carteiras",
        "sessoes",
        "usuarios",
    ):
        op.drop_table(tabela)
