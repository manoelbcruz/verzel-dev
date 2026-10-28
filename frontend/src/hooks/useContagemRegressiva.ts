import { formatarDuracao } from "../lib/datas";
import { useAgoraServidor } from "./useAgoraServidor";
export function useContagemRegressiva(alvo: string) {
  const restanteMs = Date.parse(alvo) - useAgoraServidor();
  return {
    restanteMs,
    texto: formatarDuracao(restanteMs),
    vencido: restanteMs <= 0,
    urgente: restanteMs <= 120000,
  };
}
