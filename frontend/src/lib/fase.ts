import type { Fase, LoteResumo } from "../api/tipos";
export function faseEfetiva(
  lote: Pick<LoteResumo, "fase" | "resultado" | "inicio_em" | "fim_em">,
  agora: number,
): Fase {
  if (lote.fase === "cancelado") return "cancelado";
  if (lote.resultado || agora >= Date.parse(lote.fim_em)) return "encerrado";
  return agora >= Date.parse(lote.inicio_em) ? "ao_vivo" : "agendado";
}
export function proximoLimite(lote: LoteResumo, agora: number) {
  const fase = faseEfetiva(lote, agora);
  return fase === "agendado"
    ? lote.inicio_em
    : fase === "ao_vivo"
      ? lote.fim_em
      : null;
}
