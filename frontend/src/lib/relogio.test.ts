import { estimarAmostra, relogio } from "./relogio";
afterEach(() => {
  vi.useRealTimers();
  relogio.redefinir();
});
it("estima pelo ponto médio e escolhe menor RTT entre as dez últimas", () => {
  expect(estimarAmostra(new Date(2000).toISOString(), 1000, 1800)).toEqual({
    deslocamentoMs: 600, rttMs: 800,
  });
  relogio.registrar(new Date(2000).toISOString(), 1000, 1800);
  relogio.registrar(new Date(2000).toISOString(), 1000, 1100);
  expect(relogio.deslocamento()).toBe(950);
  for (let i = 0; i < 10; i++) relogio.registrar(new Date(3000).toISOString(), 1000, 1400);
  expect(relogio.deslocamento()).toBe(1800);
  vi.useFakeTimers();
  vi.setSystemTime(5000);
  expect(relogio.agora()).toBe(6800);
});
it("usa Date no boot e depois prefere servidor_agora", () => {
  expect(relogio.sincronizado()).toBe(false);
  relogio.registrar(new Date(2000).toISOString(), 1000, 1100, false);
  expect(relogio.sincronizado()).toBe(true);
  relogio.registrar(new Date(3000).toISOString(), 1000, 1200);
  relogio.registrar(new Date(9000).toISOString(), 1000, 1001, false);
  expect(relogio.deslocamento()).toBe(1900);
});
