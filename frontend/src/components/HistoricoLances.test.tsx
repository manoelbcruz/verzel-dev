import { render, screen } from "@testing-library/react";
import HistoricoLances from "./HistoricoLances";

const MEU = "abcdefghijklmnopqrstuvwxyz";
const OUTRO = "zyxwvutsrqponmlkjihgfedcba";
const lance = (seq: number, pseudonimo: string, valor_centavos: number) => ({
  seq,
  pseudonimo,
  valor_centavos,
  instante: "2026-10-27T12:00:00Z",
  prorrogou: false,
});
const lances = [lance(2, MEU, 1000), lance(3, OUTRO, 1500)];

it("marca o próprio lance fora da dica e expõe o pseudônimo completo ao leitor de tela", () => {
  render(<HistoricoLances lances={lances} meuPseudonimo={MEU} />);
  const meu = screen.getByText(MEU).closest("li")!;
  expect(meu).toHaveTextContent("(você)");
  expect(screen.getByText(MEU)).toHaveClass("visualmente-oculto");
  expect(meu.querySelector(".dica")).not.toHaveTextContent("(você)");
  expect(screen.getByText(OUTRO).closest("li")).not.toHaveTextContent("(você)");
});
