import { fireEvent, render, screen } from "@testing-library/react";
import Dica from "./Dica";

it("mostra o texto completo no foco e no hover e fecha com Escape", () => {
  render(<Dica texto="pseudônimo completo">resumo</Dica>);
  const gatilho = screen.getByText("resumo");
  expect(gatilho).toHaveAttribute("tabindex", "0");
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  fireEvent.focus(gatilho);
  expect(screen.getByRole("tooltip")).toHaveTextContent("pseudônimo completo");
  expect(gatilho).toHaveAccessibleDescription("pseudônimo completo");
  fireEvent.keyDown(gatilho, { key: "Escape" });
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  fireEvent.blur(gatilho);
  fireEvent.mouseEnter(gatilho);
  const balao = screen.getByRole("tooltip");
  expect(balao).toHaveTextContent("pseudônimo completo");
  fireEvent.mouseLeave(gatilho, { relatedTarget: balao });
  fireEvent.mouseEnter(balao);
  expect(screen.getByRole("tooltip")).toBeInTheDocument();
  fireEvent.mouseLeave(balao);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});

it("dica não focável tem nome completo e abre só no hover", () => {
  render(<Dica texto="pseudônimo completo" focavel={false} resumo>resumo</Dica>);
  const gatilho = screen.getByText("resumo").closest(".dica")!;
  expect(gatilho).not.toHaveAttribute("tabindex");
  expect(screen.getByText("resumo")).toHaveAttribute("aria-hidden", "true");
  expect(screen.getByText("pseudônimo completo")).toHaveClass("visualmente-oculto");
  fireEvent.focus(gatilho);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  fireEvent.mouseEnter(gatilho);
  expect(screen.getByRole("tooltip")).toHaveTextContent("pseudônimo completo");
  fireEvent.mouseLeave(gatilho);
  expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
});
