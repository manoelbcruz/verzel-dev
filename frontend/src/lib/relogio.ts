type Amostra = { deslocamentoMs: number; rttMs: number; precisa: boolean };

export function estimarAmostra(servidorIso: string, antesMs: number, depoisMs: number) {
  return {
    deslocamentoMs: Date.parse(servidorIso) - (antesMs + depoisMs) / 2,
    rttMs: depoisMs - antesMs,
  };
}

let amostras: Amostra[] = [];
let tique = 0;
let timer: ReturnType<typeof setInterval> | undefined;
const assinantes = new Set<() => void>();

function avisar() {
  tique++;
  assinantes.forEach((cb) => cb());
}

export const relogio = {
  registrar(iso: string, antes: number, depois: number, precisa = true) {
    const amostra = estimarAmostra(iso, antes, depois);
    if (!Number.isFinite(amostra.deslocamentoMs) || amostra.rttMs < 0) return;
    // O Date HTTP só é usado no boot, até existir uma amostra de servidor_agora.
    if (!precisa && amostras.some((a) => a.precisa)) return;
    amostras = [...amostras, { ...amostra, precisa }].slice(-10);
    avisar();
  },
  deslocamento() {
    const preferidas = amostras.some((a) => a.precisa)
      ? amostras.filter((a) => a.precisa)
      : amostras;
    return preferidas.reduce<Amostra | undefined>(
      (melhor, a) => !melhor || a.rttMs < melhor.rttMs ? a : melhor,
      undefined,
    )?.deslocamentoMs ?? 0;
  },
  sincronizado: () => amostras.length > 0,
  agora: () => Date.now() + relogio.deslocamento(),
  tique: () => tique,
  assinarTique(cb: () => void) {
    assinantes.add(cb);
    if (!timer) timer = setInterval(avisar, 1000);
    return () => {
      assinantes.delete(cb);
      if (!assinantes.size) {
        clearInterval(timer);
        timer = undefined;
      }
    };
  },
  redefinir() {
    amostras = [];
    avisar();
  },
};
