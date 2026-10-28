import { ErroApi } from "../api/http";
import { errosPorCampo, mensagemDeErro, MENSAGENS } from "./erros";

const codigos = [
  "entrada_invalida",
  "datas_invalidas",
  "item_inelegivel",
  "chave_idempotencia_invalida",
  "nao_autenticado",
  "credenciais_invalidas",
  "papel_nao_permitido",
  "origem_invalida",
  "lote_de_outro_leiloeiro",
  "nao_encontrado",
  "lote_nao_encontrado",
  "item_nao_encontrado",
  "comprovante_nao_encontrado",
  "midia_nao_encontrada",
  "metodo_nao_permitido",
  "email_em_uso",
  "lote_nao_iniciado",
  "lote_encerrado",
  "lote_cancelado",
  "ja_esta_ganhando",
  "abaixo_do_minimo",
  "saldo_insuficiente",
  "lote_com_lances",
  "limite_saldo",
  "chave_idempotencia_conflito",
  "lote_adulterado",
  "erro_interno",
  "imagem_indisponivel",
  "api_externa_indisponivel",
  "servico_ocupado",
  "falha_rede",
  "servico_indisponivel",
];
it.each(codigos)("explica %s", (codigo) =>
  expect(mensagemDeErro(new ErroApi(400, codigo))).toBe(MENSAGENS[codigo]));

it("informa contexto, valores e mensagem desconhecida", () => {
  expect(mensagemDeErro(new ErroApi(409, "abaixo_do_minimo", "", { minimo_centavos: 1600 })))
    .toContain("R$ 16,00");
  expect(mensagemDeErro(new ErroApi(409, "saldo_insuficiente", "", { disponivel_centavos: 100 })))
    .toContain("R$ 1,00");
  expect(mensagemDeErro(new ErroApi(409, "lote_nao_iniciado"), {
    inicioEm: "2026-10-27T12:00:00Z",
  })).toContain("27/10/2026");
  expect(mensagemDeErro(new ErroApi(400, "novo", "Mensagem do servidor")))
    .toBe("Mensagem do servidor");
  expect(mensagemDeErro(new ErroApi(0, "falha_rede"), { operacao: "lance" }))
    .toContain("não será duplicado");
});

it("traduz validação do cadastro e usa orientação neutra nos outros formulários", () => {
  const erro = new ErroApi(422, "entrada_invalida", "", {
    campos: [
      { campo: "body.email", problema: "Value error, E-mail inválido" },
      {
        campo: "body.senha",
        problema: "Value should have at least 8 items after validation, not 3",
      },
    ],
  });
  expect(errosPorCampo(erro)).toEqual({
    email: "E-mail inválido", senha: "Mínimo de 8 caracteres",
  });
  expect(mensagemDeErro(erro)).toBe("Confira o valor informado.");
  expect(mensagemDeErro(erro, { operacao: "cadastro" })).toBe("Confira os campos destacados.");
});
