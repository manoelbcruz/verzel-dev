import { ErroApi } from "../api/http";
import { formatarDataHora } from "./datas";
import { formatarCentavos } from "./dinheiro";
export const MENSAGENS: Record<string, string> = {
  entrada_invalida: "Confira o valor informado.",
  datas_invalidas:
    "Datas inválidas: o início não pode estar no passado, " +
    "o fim vem depois do início e a duração vai de 1 minuto a 30 dias.",
  item_inelegivel: "Este item não é de domínio público ou não tem imagem. Escolha outro.",
  chave_idempotencia_invalida: "Falha interna do formulário. Recarregue a página e tente de novo.",
  nao_autenticado: "Entre na sua conta para continuar.",
  credenciais_invalidas: "E-mail ou senha incorretos.",
  papel_nao_permitido: "Sua conta não tem permissão para esta ação.",
  origem_invalida: "Requisição bloqueada por segurança. Recarregue a página.",
  lote_de_outro_leiloeiro: "Este lote pertence a outro leiloeiro.",
  nao_encontrado: "Página ou recurso não encontrado.",
  lote_nao_encontrado: "Lote não encontrado.",
  item_nao_encontrado: "Item não encontrado no acervo do Met.",
  comprovante_nao_encontrado: "Comprovante não encontrado. Confira o link.",
  midia_nao_encontrada: "Imagem não encontrada.",
  metodo_nao_permitido: "Operação não permitida.",
  email_em_uso: "Este e-mail já está cadastrado. Entre na sua conta.",
  lote_nao_iniciado: "Este lote ainda não começou.",
  lote_encerrado: "Este lote já encerrou e não aceita mais lances.",
  lote_cancelado: "Este lote foi cancelado.",
  ja_esta_ganhando: "Você já está ganhando este lote. Não é preciso cobrir o próprio lance.",
  abaixo_do_minimo: "Lance abaixo do mínimo.",
  saldo_insuficiente: "Saldo disponível insuficiente.",
  lote_com_lances: "Não é possível cancelar: o lote já recebeu lances.",
  limite_saldo: "O depósito ultrapassa o limite de saldo da carteira.",
  chave_idempotencia_conflito: "Esta tentativa já foi usada com outro valor. Tente de novo.",
  lote_adulterado:
    "A verificação de integridade deste lote falhou e os lances estão suspensos. " +
    "Veja a auditoria.",
  erro_interno: "Algo deu errado no servidor. Tente novamente.",
  imagem_indisponivel: "Não foi possível obter a imagem deste item no Met. Escolha outro item.",
  api_externa_indisponivel:
    "O acervo do Met está indisponível agora. " +
    "A vitrine e os lotes existentes continuam funcionando.",
  servico_ocupado: "Servidor ocupado. Tente de novo: o mesmo pedido não será duplicado.",
  falha_rede: "Sem resposta do servidor. Verifique a conexão e tente de novo.",
  servico_indisponivel: "O servidor está iniciando ou indisponível. Tente em alguns segundos.",
};
export type ContextoErro = {
  operacao?: "lance" | "deposito" | "cadastro" | "geral";
  inicioEm?: string;
};

export function mensagemDeErro(erro: unknown, contexto: ContextoErro = {}) {
  if (!(erro instanceof ErroApi)) return "Não foi possível concluir a operação.";
  if (erro.codigo === "entrada_invalida" && contexto.operacao === "cadastro") {
    return "Confira os campos destacados.";
  }
  if (erro.codigo === "falha_rede" && ["lance", "deposito"].includes(contexto.operacao ?? "")) {
    return "Sem resposta do servidor. Tente de novo: o mesmo pedido não será duplicado.";
  }
  if (erro.codigo === "papel_nao_permitido" && contexto.operacao === "lance") {
    return "Só licitantes dão lances. Leiloeiros não participam da disputa.";
  }
  if (erro.codigo === "lote_nao_iniciado" && contexto.inicioEm) {
    return `${MENSAGENS.lote_nao_iniciado} Os lances abrem em ${
      formatarDataHora(contexto.inicioEm)
    }.`;
  }
  if (erro.codigo === "abaixo_do_minimo" && Number.isSafeInteger(erro.detalhes.minimo_centavos)) {
    return `Lance abaixo do mínimo. O mínimo agora é ${
      formatarCentavos(erro.detalhes.minimo_centavos as number)
    }.`;
  }
  if (
    erro.codigo === "saldo_insuficiente" && Number.isSafeInteger(erro.detalhes.disponivel_centavos)
  ) {
    return `Saldo disponível insuficiente. Você tem ${
      formatarCentavos(erro.detalhes.disponivel_centavos as number)
    } disponível. Deposite na carteira para continuar.`;
  }
  return MENSAGENS[erro.codigo] ?? (erro.mensagem || "Não foi possível concluir a operação.");
}

export function errosPorCampo(erro: unknown): Record<string, string> {
  if (!(erro instanceof ErroApi) || !Array.isArray(erro.detalhes.campos)) return {};
  const mensagens: Record<string, string> = {};
  for (const detalhe of erro.detalhes.campos) {
    if (typeof detalhe.campo !== "string" || typeof detalhe.problema !== "string") continue;
    const campo = detalhe.campo.split(".").at(-1);
    const problema = detalhe.problema.replace(/^Value error, /, "");
    if (campo === "senha" && /too_short|at least 8/.test(detalhe.tipo ?? problema)) {
      mensagens[campo] = "Mínimo de 8 caracteres";
    } else if (campo === "senha" && /too_long|at most 128/.test(detalhe.tipo ?? problema)) {
      mensagens[campo] = "Máximo de 128 caracteres";
    } else if (campo) {
      mensagens[campo] = /^(E-mail inválido|Nome deve ter)/.test(problema)
        ? problema
        : "Confira este campo.";
    }
  }
  return mensagens;
}
