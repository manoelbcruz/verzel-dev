import { useTempoReal } from "../tempoReal/TempoRealProvider";

export function useIntervaloPolling(tipo: "sala" | "lista") {
  const { conectado } = useTempoReal();
  return tipo === "sala"
    ? conectado ? 60000 : 5000
    : conectado ? false : 15000;
}
