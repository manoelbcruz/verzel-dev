import codigo from "./dinheiro.ts?raw";
import { formatarCentavos, MAX_DEPOSITO, parseReais } from "./dinheiro";

it.each([
  [0, "R$ 0,00"],
  [1, "R$ 0,01"],
  [99, "R$ 0,99"],
  [100, "R$ 1,00"],
  [123456, "R$ 1.234,56"],
  [100000000, "R$ 1.000.000,00"],
  [1000000000000, "R$ 10.000.000.000,00"],
  [-150, "-R$ 1,50"],
])("formata %s", (valor, esperado) => expect(formatarCentavos(valor as number)).toBe(esperado));

it.each([1.5, NaN, 2 ** 53])("recusa centavos inseguros %s", (valor) =>
  expect(() => formatarCentavos(valor)).toThrow(TypeError));

it.each([
  ["1.234,56", 123456],
  ["1234,56", 123456],
  ["1234,5", 123450],
  ["1234", 123400],
  ["R$ 1.234,56", 123456],
  ["R$1.234,56", 123456],
  ["R$ 1.234,56", 123456],
  ["  10  ", 1000],
  ["0,01", 1],
  ["1234.56", 123456],
  ["1.23", 123],
  ["12.5", 1250],
  ["1.234", 123400],
  ["1.234.567,89", 123456789],
  ["10.000.000.000,00", 1000000000000],
])("converte %s", (texto, centavos) =>
  expect(parseReais(texto as string)).toEqual({ ok: true, centavos }));

it.each([
  "", " ", "abc", "1,234", "1.2345", "12,3,4", "1.23.4", "1.234.56", "-5", "+5", "1e3", "0",
  "0,00", "Infinity", "NaN", "１２", "1 234,56", "10.000.000.000,01",
])("recusa %s", (texto) => expect(parseReais(texto).ok).toBe(false));

it("limita depósitos e usa conversão inteira", () => {
  expect(parseReais("1.000.000,01", { maximo: MAX_DEPOSITO }).ok).toBe(false);
  expect(codigo).not.toMatch(/parseFloat|toFixed|Math\.round/);
  for (const centavos of [1, 99, 100, 101, 123456, 999999999999, 1000000000000]) {
    expect(parseReais(formatarCentavos(centavos))).toEqual({ ok: true, centavos });
  }
});
