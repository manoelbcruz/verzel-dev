import { act, render, screen } from "@testing-library/react";
import AvisoProrrogacao from "./AvisoProrrogacao";
it("mostra só aumento do fim do mesmo lote durante dez segundos", () => {
  vi.useFakeTimers();
  const { rerender } = render(<AvisoProrrogacao loteId="a" fimEm="2026-10-27T12:00:00Z" />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  rerender(<AvisoProrrogacao loteId="a" fimEm="2026-10-27T12:02:00Z" />);
  expect(screen.getByRole("status")).toHaveTextContent("Prorrogado");
  act(() => vi.advanceTimersByTime(10000));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  rerender(<AvisoProrrogacao loteId="b" fimEm="2026-10-27T13:00:00Z" />);
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
});
