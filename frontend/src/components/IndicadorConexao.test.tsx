import { act, render, screen } from "@testing-library/react";
import { TempoRealContext } from "../tempoReal/TempoRealProvider";
import IndicadorConexao from "./IndicadorConexao";

it("informa conexão inicial e só anuncia reconexão após cinco segundos", () => {
  vi.useFakeTimers();
  const componente = (conectado: boolean) => (
    <TempoRealContext.Provider value={{
      estado: conectado ? "conectado" : "conectando", conectado,
    }}>
      <IndicadorConexao />
    </TempoRealContext.Provider>
  );
  const { rerender } = render(componente(false));
  expect(screen.getByRole("status")).toHaveTextContent("Conectando ao tempo real");
  act(() => vi.advanceTimersByTime(4900));
  expect(screen.queryByText(/Reconectando/)).not.toBeInTheDocument();
  act(() => vi.advanceTimersByTime(100));
  expect(screen.getByRole("status")).toHaveTextContent("Reconectando");
  rerender(componente(true));
  expect(screen.getByRole("status")).toHaveTextContent("Tempo real ativo");
  rerender(componente(false));
  expect(screen.queryByText(/Reconectando/)).not.toBeInTheDocument();
});
