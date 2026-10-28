export function formatarDuracao(ms: number) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  const segundos = total % 60;
  const minutos = Math.floor(total / 60) % 60;
  const horas = Math.floor(total / 3600) % 24;
  const dois = (n: number) => String(n).padStart(2, "0");
  const fim = `${dois(minutos)}:${dois(segundos)}`;
  return total >= 86400
    ? `${Math.floor(total / 86400)} d ${dois(horas)}:${fim}`
    : total >= 3600
      ? `${dois(horas)}:${fim}`
      : fim;
}

export function formatarDuracaoFalada(ms: number) {
  let restante = Math.max(0, Math.ceil(ms / 1000));
  const partes: string[] = [];
  for (const [divisor, singular, plural] of [
    [86400, "dia", "dias"],
    [3600, "hora", "horas"],
    [60, "minuto", "minutos"],
    [1, "segundo", "segundos"],
  ] as const) {
    const valor = Math.floor(restante / divisor);
    restante %= divisor;
    if (valor) partes.push(`${valor} ${valor === 1 ? singular : plural}`);
  }
  return partes.join(" e ") || "0 segundos";
}

export const formatarDataHora = (iso: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short", timeStyle: "medium",
  }).format(new Date(iso));

export function datetimeLocalParaIso(valor: string) {
  const data = new Date(valor);
  return Number.isFinite(data.getTime()) ? data.toISOString() : null;
}

export function msParaDatetimeLocal(ms: number) {
  const data = new Date(ms);
  return new Date(ms - data.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

// Mês de 1 a 12, como no valor interno do campo.
export function diasDoMes(ano: number, mes: number) {
  const data = new Date(0);
  data.setFullYear(ano, mes, 0);
  return data.getDate();
}

export function lerCampoDataHora(texto: string): string | null {
  const partes = /^(\d{1,2})\/(\d{1,2})\/(\d{4})(?: +| *, *)(\d{1,2}):(\d{1,2})$/
    .exec(texto.trim());
  if (!partes) return null;
  const [, dia, mes, ano, hora, minuto] = partes;
  if (
    +ano < 1 || +mes < 1 || +mes > 12 || +dia < 1 ||
    +dia > diasDoMes(+ano, +mes) || +hora > 23 || +minuto > 59
  ) return null;
  const dois = (valor: string) => valor.padStart(2, "0");
  return `${ano}-${dois(mes)}-${dois(dia)}T${dois(hora)}:${dois(minuto)}`;
}

export function formatarCampoDataHora(valorInterno: string) {
  const partes = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})$/.exec(valorInterno);
  if (!partes) return "";
  const [, ano, mes, dia, hora, minuto] = partes;
  const texto = `${dia}/${mes}/${ano} ${hora}:${minuto}`;
  return lerCampoDataHora(texto) ? texto : "";
}
