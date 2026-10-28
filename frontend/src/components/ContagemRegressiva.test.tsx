import { act, render, screen } from "@testing-library/react";
import { relogio } from "../lib/relogio";
import ContagemRegressiva from "./ContagemRegressiva";
it("conta pelo servidor, acompanha prorrogação e anuncia o vencimento sem aria-live", () => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-10-27T12:00:00Z"));
  relogio.registrar("2026-10-27T12:01:30Z", Date.now(), Date.now());
  const { rerender } = render(<ContagemRegressiva alvo="2026-10-27T12:03:35Z" />);
  expect(screen.getByText("02:05")).not.toHaveAttribute("aria-live");
  act(() => vi.advanceTimersByTime(5000));
  expect(screen.getByText("02:00")).toHaveAttribute("data-urgente", "true");
  rerender(<ContagemRegressiva alvo="2026-10-27T12:04:35Z" />);
  expect(screen.getByText("03:00")).toBeInTheDocument();
  act(() => vi.advanceTimersByTime(180000));
  expect(screen.getByText("Encerrando…")).toBeInTheDocument();
});
