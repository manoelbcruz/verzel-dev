import { useEffect } from "react";
import { relogio } from "../lib/relogio";
export function useRefetchNosLimites(
  refetch: () => unknown,
  limites: (string | null | undefined)[],
) {
  const chave = limites.filter((v): v is string => !!v).join("|");
  const deslocamento = relogio.deslocamento();
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    function armar() {
      const futuros = chave.split("|").map(Date.parse).filter((t) => t + 1000 > relogio.agora());
      if (!futuros.length) return;
      const alvo = Math.min(...futuros) + 1000;
      const espera = alvo - relogio.agora();
      timer = setTimeout(() => {
        if (alvo > relogio.agora()) armar();
        else {
          void refetch();
          armar();
        }
      }, Math.max(0, Math.min(2147483647, espera)));
    }
    armar();
    return () => clearTimeout(timer);
  }, [chave, refetch, deslocamento]);
}
