import type { Fase } from "../api/tipos";

export const ROTULOS_FASE = {
  agendado: "Agendado",
  ao_vivo: "Ao vivo",
  encerrado: "Encerrado",
  cancelado: "Cancelado",
};

export default function SeloFase({ fase }: { fase: Fase }) {
  return <span className={`selo selo-${fase}`}>{ROTULOS_FASE[fase]}</span>;
}
