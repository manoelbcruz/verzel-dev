import type { QueryClient, QueryKey } from "@tanstack/react-query";
import type { Mensagem } from "./mensagens";

export function criarDespachante(
  cliente: QueryClient,
  { atrasoMs = 150, atrasoListasMs = 400 } = {},
) {
  const timers = new Map<string, ReturnType<typeof setTimeout>>();
  const pendentes = new Map<string, QueryKey>();
  let parado = false;
  const desassinar = cliente.getQueryCache().subscribe((evento) => {
    const query = evento.query;
    if (!pendentes.has(query.queryHash) || query.state.fetchStatus === "fetching") return;
    const chave = pendentes.get(query.queryHash)!;
    pendentes.delete(query.queryHash);
    if (evento.type === "removed") return;
    // A primeira leitura pode ter começado antes do evento. Refaz depois dela.
    queueMicrotask(() => {
      if (!parado) {
        void cliente.invalidateQueries({ queryKey: chave, exact: true, refetchType: "active" });
      }
    });
  });
  function invalidar(chave: QueryKey) {
    for (const query of cliente.getQueryCache().findAll({ queryKey: chave })) {
      if (query.state.fetchStatus === "fetching") pendentes.set(query.queryHash, query.queryKey);
    }
    void cliente.invalidateQueries(
      { queryKey: chave, refetchType: "active" },
      { cancelRefetch: false },
    );
  }
  function agendar(chave: QueryKey, atraso: number) {
    const id = JSON.stringify(chave);
    if (timers.has(id)) return;
    timers.set(id, setTimeout(() => {
      timers.delete(id);
      invalidar(chave);
    }, atraso));
  }
  return {
    despachar(msg: Mensagem) {
      if (parado) return;
      if (msg.tipo === "ola") {
        for (const nome of [
          "sessao", "vitrine", "lote", "carteira", "participacoes", "painel", "auditoria",
        ]) {
          invalidar([nome]);
        }
      } else if (msg.tipo === "carteira_atualizada") {
        for (const nome of ["carteira", "participacoes", "painel"]) agendar([nome], atrasoMs);
      } else if ("lote_id" in msg) {
        const id = msg.lote_id.toLowerCase();
        const cache = cliente.getQueryData<{ versao: number }>(["lote", id]);
        if (!cache || cache.versao < msg.versao) agendar(["lote", id], atrasoMs);
        agendar(["auditoria", id], atrasoMs);
        for (const nome of ["vitrine", "painel", "participacoes"]) agendar([nome], atrasoListasMs);
      }
    },
    parar() {
      parado = true;
      timers.forEach(clearTimeout);
      timers.clear();
      pendentes.clear();
      desassinar();
    },
  };
}
