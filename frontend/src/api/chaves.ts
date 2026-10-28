export const chaves = {
  sessao: ["sessao"] as const,
  vitrine: (q = "") => ["vitrine", q] as const,
  lote: (id: string) => ["lote", id.toLowerCase()] as const,
  carteira: ["carteira"] as const,
  participacoes: ["participacoes"] as const,
  painel: ["painel"] as const,
  auditoria: (id: string) => ["auditoria", id.toLowerCase()] as const,
  comprovante: (codigo: string) => ["comprovante", codigo] as const,
  itens: (q: string, pagina: number) => ["itens", q, pagina] as const,
};
