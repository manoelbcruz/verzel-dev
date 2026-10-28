export type TipoLote = "lote_publicado" | "lote_atualizado" | "lote_cancelado" | "lote_encerrado";
export type Mensagem =
  | { v: 1; tipo: "ola"; autenticado: boolean }
  | { v: 1; tipo: "ping" | "carteira_atualizada" }
  | { v: 1; tipo: TipoLote; lote_id: string; versao: number };

export function interpretarMensagem(texto: string): Mensagem | null {
  try {
    const msg = JSON.parse(texto);
    if (!msg || msg.v !== 1) return null;
    if (msg.tipo === "ola") {
      return typeof msg.autenticado === "boolean"
        ? { v: 1, tipo: "ola", autenticado: msg.autenticado }
        : null;
    }
    if (["ping", "carteira_atualizada"].includes(msg.tipo)) {
      return { v: 1, tipo: msg.tipo };
    }
    if (
      [
        "lote_publicado", "lote_atualizado", "lote_cancelado", "lote_encerrado",
      ].includes(msg.tipo) &&
      typeof msg.lote_id === "string" &&
      Number.isSafeInteger(msg.versao) &&
      msg.versao > 0
    ) {
      return { v: 1, tipo: msg.tipo, lote_id: msg.lote_id.toLowerCase(), versao: msg.versao };
    }
  } catch {
    /* Frame inválido não altera estado nem cache. */
  }
  return null;
}
