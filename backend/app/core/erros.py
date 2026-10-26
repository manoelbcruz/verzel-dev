MENSAGENS = {
    "entrada_invalida": "Confira os campos informados.",
    "datas_invalidas": "As datas do lote são inválidas.",
    "item_inelegivel": "Este item não pode ser leiloado.",
    "chave_idempotencia_invalida": "Informe uma Idempotency-Key válida.",
    "nao_autenticado": "Entre na sua conta para continuar.",
    "credenciais_invalidas": "E-mail ou senha inválidos.",
    "papel_nao_permitido": "Seu papel não permite esta operação.",
    "origem_invalida": "Origem da requisição não permitida.",
    "lote_de_outro_leiloeiro": "O lote pertence a outro leiloeiro.",
    "nao_encontrado": "Recurso não encontrado.",
    "lote_nao_encontrado": "Lote não encontrado.",
    "item_nao_encontrado": "Item não encontrado.",
    "comprovante_nao_encontrado": "Comprovante não encontrado.",
    "midia_nao_encontrada": "Imagem não encontrada.",
    "metodo_nao_permitido": "Método não permitido.",
    "email_em_uso": "Este e-mail já está cadastrado.",
    "lote_nao_iniciado": "O lote ainda não começou.",
    "lote_encerrado": "O lote já encerrou.",
    "lote_cancelado": "O lote foi cancelado.",
    "ja_esta_ganhando": "Você já está ganhando este lote.",
    "abaixo_do_minimo": "O lance está abaixo do mínimo.",
    "saldo_insuficiente": "Saldo disponível insuficiente.",
    "lote_com_lances": "Não é possível cancelar um lote com lances.",
    "limite_saldo": "O depósito excede o limite de saldo.",
    "chave_idempotencia_conflito": "Esta chave já foi usada com outra entrada.",
    "lote_adulterado": "A integridade do lote não confere.",
    "erro_interno": "Não foi possível concluir a operação.",
    "imagem_indisponivel": "A imagem está indisponível.",
    "api_externa_indisponivel": "A consulta ao Met está indisponível.",
    "servico_ocupado": "Serviço ocupado; tente novamente com a mesma chave.",
}
STATUS = {
    codigo: status
    for status, codigos in {
        422: "entrada_invalida datas_invalidas item_inelegivel",
        400: "chave_idempotencia_invalida",
        401: "nao_autenticado credenciais_invalidas",
        403: "papel_nao_permitido origem_invalida lote_de_outro_leiloeiro",
        404: "nao_encontrado lote_nao_encontrado item_nao_encontrado "
        "comprovante_nao_encontrado midia_nao_encontrada",
        405: "metodo_nao_permitido",
        409: "email_em_uso lote_nao_iniciado lote_encerrado lote_cancelado ja_esta_ganhando "
        "abaixo_do_minimo saldo_insuficiente lote_com_lances limite_saldo "
        "chave_idempotencia_conflito lote_adulterado",
        500: "erro_interno",
        502: "imagem_indisponivel",
        503: "api_externa_indisponivel servico_ocupado",
    }.items()
    for codigo in codigos.split()
}


class ErroApi(Exception):
    def __init__(self, status: int, codigo: str, mensagem: str | None = None, detalhes=None):
        self.status = status
        self.codigo = codigo
        self.mensagem = mensagem or MENSAGENS[codigo]
        self.detalhes = detalhes or {}
        super().__init__(self.mensagem)

    def corpo(self) -> dict:
        return {
            "erro": {"codigo": self.codigo, "mensagem": self.mensagem, "detalhes": self.detalhes}
        }


class Recusa(ErroApi):
    def __init__(self, codigo: str, detalhes=None):
        super().__init__(STATUS[codigo], codigo, detalhes=detalhes)


class ErroIntegridade(Recusa):
    def __init__(self, codigo: str, seq: int | None = None):
        super().__init__("lote_adulterado", {"falha": codigo, "seq": seq})


class ErroCarteiraDivergente(ErroIntegridade):
    def __init__(self, lote_id, carteira_id: int):
        super().__init__("carteira_divergente")
        # Contexto operacional para o log; não integra o corpo público do erro.
        self.lote_id = lote_id
        self.carteira_id = carteira_id


class ApiExternaIndisponivel(Recusa):
    def __init__(self):
        super().__init__("api_externa_indisponivel")
