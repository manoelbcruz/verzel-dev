export type Papel = "leiloeiro" | "licitante";
export type Usuario = { nome: string; email: string; papel: Papel };
export type LoginEntrada = { email: string; senha: string };
export type CadastroEntrada = LoginEntrada & { nome: string; papel: Papel };
export type Fase = "agendado" | "ao_vivo" | "encerrado" | "cancelado";

export type Resultado = {
  situacao: "arrematado" | "sem_lances";
  valor_centavos: number | null;
  vencedor_pseudonimo: string | null;
  encerrado_em: string;
  comprovante_codigo: string | null;
};

export type LoteResumo = {
  id: string;
  titulo: string;
  imagem_url: string;
  fase: Fase;
  inicio_em: string;
  fim_em: string;
  lance_inicial_centavos: number;
  lance_atual_centavos: number | null;
  total_lances: number;
  resultado: Resultado | null;
};

export type MinhaParticipacao = {
  meu_pseudonimo: string;
  ganhando: boolean;
  meu_maior_lance_centavos: number;
  posicao: number;
  total_participantes: number;
};

export type LanceHistorico = {
  seq: number;
  pseudonimo: string;
  valor_centavos: number;
  instante: string;
  prorrogou: boolean;
};

export type LoteDetalhe = LoteResumo & {
  atributos: Record<string, string>;
  incremento_centavos: number;
  fim_original_em: string;
  proximo_lance_minimo_centavos: number;
  lider_pseudonimo: string | null;
  versao: number;
  servidor_agora: string;
  lances: LanceHistorico[];
  minha_participacao: MinhaParticipacao | null;
  cancelavel: boolean;
};

export type LanceAceito = {
  lote_id: string;
  seq: number;
  valor_centavos: number;
  instante: string;
  fim_em: string;
  prorrogou: boolean;
  lider_pseudonimo: string;
  proximo_lance_minimo_centavos: number;
};

export type LoteEntrada = {
  item_id_externo: string;
  lance_inicial_centavos: number;
  incremento_centavos: number;
  inicio_em: string;
  fim_em: string;
};

export type Vitrine = {
  servidor_agora: string;
  ao_vivo: LoteResumo[];
  agendados: LoteResumo[];
  encerrados: LoteResumo[];
};

export type LotePainel = LoteResumo & { cancelavel: boolean };
export type PainelLeiloeiro = { total_recebido_centavos: number; lotes: LotePainel[] };

export type Participacao = {
  lote: LoteResumo;
  meu_pseudonimo: string;
  meu_maior_lance_centavos: number;
  situacao: "ganhando" | "superado" | "aguardando_resultado" | "arrematado" | "nao_arrematado";
  comprovante_codigo: string | null;
};

export type Carteira = {
  saldo_total_centavos: number;
  comprometido_centavos: number;
  disponivel_centavos: number;
  reservas: { lote_id: string; titulo: string; valor_centavos: number }[];
  lancamentos: {
    tipo: "deposito" | "arremate_debito" | "arremate_credito";
    valor_centavos: number;
    criado_em: string;
    lote_id: string | null;
  }[];
};

export type ItemExterno = {
  id_externo: string;
  titulo: string;
  atributos: Record<string, string>;
  imagem_url_externa: string;
};

export type PaginaItens = {
  pagina: number;
  por_pagina: number;
  total_ids: number;
  tem_mais: boolean;
  parcial: boolean;
  origem: "api" | "cache";
  itens: ItemExterno[];
};

export type RelatorioAuditoria = {
  lote_id: string;
  titulo: string;
  imagem_url: string;
  fase: Fase;
  veredito: "integro" | "adulterado";
  metodo: string;
  total_eventos: number;
  eventos_verificados: number;
  falha: { codigo: string; seq: number | null; mensagem: string } | null;
  verificado_em: string;
  eventos: {
    seq: number;
    tipo: string;
    instante: string;
    licitante_pseudonimo: string | null;
    valor_centavos: number | null;
    fim_novo: string | null;
    prorrogou: boolean;
    mac: string;
    verificado: boolean;
  }[];
};

export type Comprovante = {
  codigo: string;
  lote_id: string;
  titulo: string;
  atributos: Record<string, string>;
  imagem_url: string;
  valor_centavos: number;
  vencedor_pseudonimo: string;
  encerrado_em: string;
  evento_encerramento: { seq: number; mac: string };
  auditoria_url: string;
};

export type ContasDemo = {
  contas: { papel: Papel; email: string; rotulo: string }[];
  senha: string | null;
};
