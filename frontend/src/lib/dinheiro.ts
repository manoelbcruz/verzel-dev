export const MAX_CENTAVOS = 1_000_000_000_000;
export const MAX_DEPOSITO = 100_000_000;

export function formatarCentavos(valor: number): string {
  if (!Number.isSafeInteger(valor)) throw new TypeError("Centavos precisam ser inteiros seguros");
  const absoluto = Math.abs(valor);
  const resto = absoluto % 100;
  const reais = String((absoluto - resto) / 100).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${valor < 0 ? "-" : ""}R$\u00a0${reais},${String(resto).padStart(2, "0")}`;
}

export function parseReais(
  texto: string,
  { maximo = MAX_CENTAVOS } = {},
): { ok: true; centavos: number } | { ok: false; erro: string } {
  const valor = texto.trim().replace(/^R\$[ \u00a0]*/, "");
  let partes: string[];
  if (/^\d{1,3}(\.\d{3})*(,\d{1,2})?$/.test(valor) || /^\d+(,\d{1,2})?$/.test(valor)) {
    partes = valor.replace(/\./g, "").split(",");
  } else if (/^\d+\.\d{1,2}$/.test(valor)) {
    partes = valor.split(".");
  } else return { ok: false, erro: "Use o formato 1.234,56" };
  const centavos =
    Number.parseInt(partes[0], 10) * 100 + Number.parseInt((partes[1] ?? "").padEnd(2, "0"), 10);
  if (!Number.isSafeInteger(centavos) || centavos > maximo) {
    return { ok: false, erro: `O valor máximo é ${formatarCentavos(maximo)}` };
  }
  if (centavos === 0) return { ok: false, erro: "O valor precisa ser maior que zero" };
  return { ok: true, centavos };
}
