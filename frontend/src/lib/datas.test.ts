import {
  datetimeLocalParaIso, diasDoMes, formatarCampoDataHora, formatarDuracao,
  lerCampoDataHora, msParaDatetimeLocal,
} from "./datas";
it("formata duração nas três faixas e converte datas locais", () => {
  expect(formatarDuracao(125000)).toBe("02:05");
  expect(formatarDuracao(14706000)).toBe("04:05:06");
  expect(formatarDuracao(3 * 86400000 + 14706000)).toBe("3 d 04:05:06");
  const ms = Date.parse("2026-10-27T12:30:00Z");
  expect(datetimeLocalParaIso(msParaDatetimeLocal(ms))).toBe(new Date(ms).toISOString());
  expect(datetimeLocalParaIso("inválido")).toBeNull();
});

it.each([
  ["2026-10-28T14:30", "28/10/2026 14:30"],
  ["2026-01-02T00:05", "02/01/2026 00:05"],
  ["2028-02-29T23:59", "29/02/2028 23:59"],
  ["0099-01-01T00:00", "01/01/0099 00:00"],
])("converte %s de ida e volta sem mudar o fuso", (interno, texto) => {
  expect(formatarCampoDataHora(interno)).toBe(texto);
  expect(lerCampoDataHora(texto)).toBe(interno);
});

it.each([
  "31/02/2026 10:00", "29/02/2026 10:00", "00/01/2026 10:00", "01/13/2026 10:00",
  "01/00/2026 10:00", "01/01/0000 10:00", "01/01/2026 24:00", "01/01/2026 10:60",
  "01/01/10000 10:00", "28/10/2026 14:", "", "2026-10-28T14:30",
])("recusa data inexistente ou formato inválido: %s", (texto) => {
  expect(lerCampoDataHora(texto)).toBeNull();
});

it("conta dias em fevereiro, anos seculares e meses de trinta e trinta e um dias", () => {
  expect(diasDoMes(2026, 2)).toBe(28);
  expect(diasDoMes(2028, 2)).toBe(29);
  expect(diasDoMes(1900, 2)).toBe(28);
  expect(diasDoMes(2000, 2)).toBe(29);
  expect(diasDoMes(2026, 4)).toBe(30);
  expect(diasDoMes(2026, 1)).toBe(31);
  expect(formatarCampoDataHora("")).toBe("");
  expect(formatarCampoDataHora("2026-02-31T10:00")).toBe("");
});

it.each([
  [" 28/10/2026 14:30 ", "2026-10-28T14:30"],
  ["28/10/2026,14:30", "2026-10-28T14:30"],
  ["28/10/2026, 14:30", "2026-10-28T14:30"],
  ["28/10/2026 , 14:30", "2026-10-28T14:30"],
  ["1/1/2026 9:00", "2026-01-01T09:00"],
  ["1/1/2026 9:5", "2026-01-01T09:05"],
  ["1/1/0001 0:0", "0001-01-01T00:00"],
  ["31/12/9999 23:59", "9999-12-31T23:59"],
])("aceita e normaliza %s", (texto, interno) => {
  expect(lerCampoDataHora(texto)).toBe(interno);
});
