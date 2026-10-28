import { fireEvent, render, screen, within } from "@testing-library/react";
import SeletorTema from "./SeletorTema";

it("aplica tema escuro, marca a escolha e permite voltar ao sistema", () => {
  render(<SeletorTema />);
  const grupo = screen.getByRole("group", { name: "Tema" });
  const escuro = within(grupo).getByRole("button", { name: "Tema escuro" });
  fireEvent.click(escuro);
  expect(document.documentElement).toHaveClass("dark");
  expect(escuro).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Tema claro" }))
    .toHaveAttribute("aria-pressed", "false");
  fireEvent.click(screen.getByRole("button", { name: "Tema do sistema" }));
  expect(document.documentElement).not.toHaveClass("dark");
  expect(escuro).toHaveAttribute("aria-pressed", "false");
});

it.each([
  ["Tema claro", "Tema claro"],
  ["Tema escuro", "Tema escuro"],
  ["Tema do sistema", "Seguir o sistema"],
])("mostra dica de %s sem acrescentar parada de Tab", (nome, dica) => {
  render(<SeletorTema />);
  const botao = screen.getByRole("button", { name: nome });
  expect(botao.parentElement).not.toHaveAttribute("tabindex");
  fireEvent.focus(botao);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  fireEvent.mouseEnter(botao);
  expect(screen.getByRole("tooltip")).toHaveTextContent(dica);
  expect(botao).toHaveAccessibleName(nome);
});
