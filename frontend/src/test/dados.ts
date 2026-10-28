import type {
  Carteira,
  Comprovante,
  LoteDetalhe,
  RelatorioAuditoria,
  Usuario,
  Vitrine,
} from "../api/tipos";

export const ANA: Usuario = {
  nome: "Ana de teste", email: "ana@example.test", papel: "licitante",
};
export const BRUNO: Usuario = {
  nome: "Bruno de teste", email: "bruno@example.test", papel: "licitante",
};
export const LEILOEIRO: Usuario = {
  nome: "Casa de teste", email: "casa@example.test", papel: "leiloeiro",
};
export const ID = "0f8fad5b-d9cb-469f-a165-70867728950e";

export function lote(alteracoes: Partial<LoteDetalhe> = {}): LoteDetalhe {
  const agora = Date.now();
  return {
    id: ID,
    titulo: "Obra do acervo",
    imagem_url: "/api/midias/imagem",
    atributos: { artista: "Artista", licenca: "CC0" },
    fase: "ao_vivo",
    inicio_em: new Date(agora - 60000).toISOString(),
    fim_em: new Date(agora + 3600000).toISOString(),
    fim_original_em: new Date(agora + 3600000).toISOString(),
    lance_inicial_centavos: 1500,
    incremento_centavos: 100,
    lance_atual_centavos: null,
    total_lances: 0,
    resultado: null,
    proximo_lance_minimo_centavos: 1500,
    lider_pseudonimo: null,
    versao: 1,
    servidor_agora: new Date(agora).toISOString(),
    lances: [],
    minha_participacao: null,
    cancelavel: false,
    ...alteracoes,
  };
}

export const carteira = (saldo = 100000): Carteira => ({
  saldo_total_centavos: saldo,
  comprometido_centavos: 2000,
  disponivel_centavos: saldo - 2000,
  reservas: [],
  lancamentos: [],
});

export const vitrine = (alteracoes: Partial<Vitrine> = {}): Vitrine => ({
  servidor_agora: new Date().toISOString(),
  ao_vivo: [],
  agendados: [],
  encerrados: [],
  ...alteracoes,
});

export const comprovante = (): Comprovante => ({
  codigo: "codigo-publico",
  lote_id: ID,
  titulo: "Obra arrematada",
  imagem_url: "/api/midias/imagem",
  atributos: { licenca: "CC0" },
  valor_centavos: 1600,
  vencedor_pseudonimo: "Pessoa-vencedora",
  encerrado_em: new Date().toISOString(),
  evento_encerramento: { seq: 4, mac: "a".repeat(64) },
  auditoria_url: `/api/lotes/${ID}/auditoria`,
});

export const auditoria = (): RelatorioAuditoria => ({
  lote_id: ID,
  titulo: "Obra auditada",
  imagem_url: "/api/midias/imagem",
  fase: "ao_vivo",
  veredito: "integro",
  metodo: "hmac-sha256-cadeia-por-lote-v1",
  total_eventos: 1,
  eventos_verificados: 1,
  falha: null,
  verificado_em: new Date().toISOString(),
  eventos: [{
    seq: 1,
    tipo: "publicacao",
    instante: new Date().toISOString(),
    licitante_pseudonimo: null,
    valor_centavos: null,
    fim_novo: null,
    prorrogou: false,
    mac: "b".repeat(64),
    verificado: true,
  }],
});

export const recusa = (codigo: string, detalhes: Record<string, unknown> = {}, status = 409) =>
  new Response(JSON.stringify({ erro: { codigo, mensagem: "Recusa do servidor", detalhes } }), {
    status,
    headers: { "Content-Type": "application/json" },
  });

export function promessa<T>() {
  let liberar!: (valor: T) => void;
  const pendente = new Promise<T>((resolve) => { liberar = resolve; });
  return { pendente, liberar };
}
