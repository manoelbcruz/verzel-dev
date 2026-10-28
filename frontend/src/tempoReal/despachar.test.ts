import { QueryClient, QueryObserver } from "@tanstack/react-query";
import { waitFor } from "@testing-library/react";
import { criarDespachante } from "./despachar";

it("coalesce por chave, respeita versão e invalida listas", () => {
  vi.useFakeTimers();
  const cliente = new QueryClient();
  const invalidar = vi.spyOn(cliente, "invalidateQueries");
  cliente.setQueryData(["lote", "x"], { versao: 5 });
  const d = criarDespachante(cliente);
  d.despachar({ v: 1, tipo: "lote_atualizado", lote_id: "x", versao: 4 });
  vi.advanceTimersByTime(400);
  expect(invalidar).not.toHaveBeenCalledWith(
    expect.objectContaining({ queryKey: ["lote", "x"] }), expect.anything(),
  );
  invalidar.mockClear();
  for (let versao = 6; versao <= 8; versao++) {
    d.despachar({ v: 1, tipo: "lote_atualizado", lote_id: "x", versao });
  }
  vi.advanceTimersByTime(150);
  expect(invalidar.mock.calls.filter(([f]) => JSON.stringify(f?.queryKey) === '["lote","x"]'))
    .toHaveLength(1);
  vi.advanceTimersByTime(250);
  for (const chave of [["vitrine"], ["painel"], ["participacoes"], ["auditoria", "x"]]) {
    expect(invalidar).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: chave }), expect.anything(),
    );
  }
  d.despachar({ v: 1, tipo: "carteira_atualizada" });
  vi.advanceTimersByTime(150);
  expect(invalidar).toHaveBeenCalledWith(
    expect.objectContaining({ queryKey: ["carteira"] }), expect.anything(),
  );
  invalidar.mockClear();
  d.despachar({ v: 1, tipo: "ola", autenticado: false });
  expect(invalidar.mock.calls.map(([f]) => f?.queryKey)).toEqual([
    "sessao", "vitrine", "lote", "carteira", "participacoes", "painel", "auditoria",
  ].map((k) => [k]));
  d.parar();
  cliente.clear();
});

it("ola durante GET força segunda leitura e converge sem outro evento", async () => {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  let liberar!: (valor: number) => void;
  const ler = vi.fn()
    .mockImplementationOnce(() => new Promise<number>((r) => { liberar = r; }))
    .mockResolvedValue(2);
  const observador = new QueryObserver(cliente, { queryKey: ["lote", "x"], queryFn: ler });
  const cancelar = observador.subscribe(() => {});
  const d = criarDespachante(cliente);
  expect(ler).toHaveBeenCalledTimes(1);
  d.despachar({ v: 1, tipo: "ola", autenticado: false });
  liberar(1);
  await waitFor(() => expect(cliente.getQueryData(["lote", "x"])).toBe(2));
  expect(ler).toHaveBeenCalledTimes(2);
  d.parar();
  cancelar();
  cliente.clear();
});
