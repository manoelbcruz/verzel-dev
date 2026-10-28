import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import CampoDataHora from "./CampoDataHora";
import { relogio } from "../lib/relogio";

function montar(valor = "2026-10-28T14:30") {
  const aoMudar = vi.fn();
  render(<CampoDataHora rotulo="Início" valor={valor} aoMudar={aoMudar} />);
  const campo = screen.getByLabelText("Início");
  const abrir = screen.getByRole("button", { name: "Abrir calendário de Início" });
  return { aoMudar, campo, abrir };
}

it("converte a digitação completa e válida para o formato interno", () => {
  const { campo, aoMudar } = montar("");
  fireEvent.change(campo, { target: { value: "28/10/2026 14:30" } });
  expect(aoMudar).toHaveBeenCalledExactlyOnceWith("2026-10-28T14:30");
});

it.each(["31/02/2026 10:00", "28/10/2026 14:"])(
  "mantém %s como rascunho e explica o formato no blur", (texto) => {
    const { campo, aoMudar } = montar();
    fireEvent.change(campo, { target: { value: texto } });
    expect(aoMudar).not.toHaveBeenCalled();
    expect(screen.queryByText("Use o formato dd/mm/aaaa hh:mm")).not.toBeInTheDocument();
    fireEvent.blur(campo);
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(campo).toHaveAccessibleDescription("Use o formato dd/mm/aaaa hh:mm");
  },
);

it("apaga o valor e sincroniza atualizações externas", () => {
  function Controlado() {
    const [valor, setValor] = useState("2026-10-28T14:30");
    return <>
      <CampoDataHora rotulo="Início" valor={valor} aoMudar={setValor} />
      <output>{valor || "Vazio"}</output>
      <button onClick={() => setValor("2026-11-01T00:05")}>Atualizar</button>
    </>;
  }
  render(<Controlado />);
  fireEvent.change(screen.getByLabelText("Início"), { target: { value: "" } });
  expect(screen.getByText("Vazio")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Atualizar" }));
  expect(screen.getByLabelText("Início")).toHaveValue("01/11/2026 00:05");
});

it("navega por mês, escolhe dia e horário e aplica", () => {
  const { abrir, aoMudar, campo } = montar();
  fireEvent.click(abrir);
  expect(screen.getByRole("dialog", { name: "Escolher Início" })).toBeInTheDocument();
  expect(screen.getByText("outubro de 2026")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Mês seguinte" }));
  fireEvent.click(screen.getByRole("button", { name: "quinta-feira, 5 de novembro de 2026" }));
  fireEvent.change(screen.getByLabelText("Hora"), { target: { value: "09" } });
  fireEvent.change(screen.getByLabelText("Minuto"), { target: { value: "05" } });
  expect(aoMudar).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
  expect(aoMudar).toHaveBeenCalledExactlyOnceWith("2026-11-05T09:05");
  expect(campo).toHaveValue("05/11/2026 09:05");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(abrir).toHaveFocus();
});

it.each(["Escape", "Cancelar", "fora"])("fecha com %s sem aplicar e devolve foco",
  async (modo) => {
    const { abrir, aoMudar } = montar();
    fireEvent.click(abrir);
    const dia = screen.getByRole("button", { name: "quarta-feira, 28 de outubro de 2026" });
    expect(dia).toHaveFocus();
    fireEvent.click(screen.getByRole("button", { name: "quinta-feira, 29 de outubro de 2026" }));
    if (modo === "Escape") fireEvent.keyDown(dia, { key: "Escape" });
    else if (modo === "Cancelar") fireEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    else fireEvent.pointerDown(document.body);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(aoMudar).not.toHaveBeenCalled();
    await waitFor(() => expect(abrir).toHaveFocus());
    expect(abrir).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(abrir);
    expect(screen.getByRole("button", { name: "quarta-feira, 28 de outubro de 2026" }))
      .toHaveAttribute("aria-pressed", "true");
  },
);

it("setas percorrem dias, semanas e fronteiras de mês", () => {
  const { abrir, aoMudar } = montar("2026-10-31T14:30");
  fireEvent.click(abrir);
  fireEvent.keyDown(document.activeElement!, { key: "ArrowRight" });
  expect(screen.getByRole("button", { name: "domingo, 1 de novembro de 2026" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "ArrowDown" });
  expect(screen.getByRole("button", { name: "domingo, 8 de novembro de 2026" })).toHaveFocus();
  fireEvent.keyDown(document.activeElement!, { key: "ArrowLeft" });
  fireEvent.keyDown(document.activeElement!, { key: "ArrowUp" });
  expect(screen.getByRole("button", { name: "sábado, 31 de outubro de 2026" })).toHaveFocus();
  expect(aoMudar).not.toHaveBeenCalled();
});

it("valida hora e minuto antes de aplicar", () => {
  const { abrir, aoMudar } = montar();
  fireEvent.click(abrir);
  const hora = screen.getByLabelText("Hora");
  const minuto = screen.getByLabelText("Minuto");
  fireEvent.change(hora, { target: { value: "24" } });
  fireEvent.change(minuto, { target: { value: "60" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
  expect(aoMudar).not.toHaveBeenCalled();
  expect(hora).toHaveFocus();
  expect(screen.getByRole("alert")).toHaveTextContent("hora de 00 a 23 e minuto de 00 a 59");
  fireEvent.change(hora, { target: { value: "0" } });
  fireEvent.click(screen.getByRole("button", { name: "Aplicar" }));
  expect(minuto).toHaveFocus();
  fireEvent.change(minuto, { target: { value: "0" } });
  fireEvent.keyDown(minuto, { key: "Enter" });
  expect(aoMudar).toHaveBeenCalledExactlyOnceWith("2026-10-28T00:00");
});

it("usa o relógio do servidor para o mês inicial e o destaque de hoje", () => {
  const agora = vi.spyOn(relogio, "agora").mockReturnValue(new Date(2031, 0, 2, 10).getTime());
  try {
    const { abrir } = montar("");
    fireEvent.click(abrir);
    expect(screen.getByText("janeiro de 2031")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "quinta-feira, 2 de janeiro de 2031" }))
      .toHaveAttribute("aria-current", "date");
  } finally {
    agora.mockRestore();
  }
});

it("desabilita entrada e calendário", () => {
  render(<CampoDataHora rotulo="Fim" valor="" aoMudar={vi.fn()} desabilitado />);
  expect(screen.getByLabelText("Fim")).toBeDisabled();
  expect(screen.getByRole("button", { name: "Abrir calendário de Fim" })).toBeDisabled();
});

it.each([
  [" 28/10/2026 14:30 ", "28/10/2026 14:30"],
  ["28/10/2026,14:30", "28/10/2026 14:30"],
  ["28/10/2026, 14:30", "28/10/2026 14:30"],
  ["1/1/2026 9:00", "01/01/2026 09:00"],
  ["1/1/2026 9:5", "01/01/2026 09:05"],
])("normaliza %s ao sair do campo", (texto, completo) => {
  const { campo, aoMudar } = montar("");
  fireEvent.change(campo, { target: { value: texto } });
  expect(aoMudar).toHaveBeenCalledOnce();
  expect(campo).toHaveValue(texto);
  fireEvent.blur(campo);
  expect(campo).toHaveValue(completo);
  expect(campo).toHaveAttribute("aria-invalid", "false");
});

it("fecha sem aplicar quando Tab leva o foco de Aplicar ao campo seguinte", () => {
  const { abrir, aoMudar } = montar();
  render(<input aria-label="Campo seguinte" />);
  fireEvent.click(abrir);
  act(() => screen.getByRole("button", { name: "Aplicar" }).focus());
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  fireEvent.keyDown(document.activeElement!, { key: "Tab" });
  // jsdom não executa a navegação padrão de Tab; o foco gera o blur real da raiz.
  act(() => screen.getByLabelText("Campo seguinte").focus());
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(screen.getByLabelText("Campo seguinte")).toHaveFocus();
  expect(aoMudar).not.toHaveBeenCalled();
});

it("continua aberto quando o foco cai no body por clique em área vazia do painel", () => {
  const { abrir, aoMudar } = montar();
  fireEvent.click(abrir);
  const dia = screen.getByRole("dialog").querySelector<HTMLButtonElement>("button[tabindex='0']")!;
  act(() => dia.focus());
  act(() => dia.blur());
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(aoMudar).not.toHaveBeenCalled();
});

it("preserva a digitação abreviada no campo controlado até o blur", () => {
  function Controlado() {
    const [valor, setValor] = useState("");
    return <>
      <CampoDataHora rotulo="Início" valor={valor} aoMudar={setValor} />
      <output>{valor}</output>
    </>;
  }
  render(<Controlado />);
  const campo = screen.getByLabelText("Início");
  fireEvent.change(campo, { target: { value: "1/1/2026 9:3" } });
  expect(campo).toHaveValue("1/1/2026 9:3");
  expect(screen.getByRole("status")).toHaveTextContent("2026-01-01T09:03");
  fireEvent.change(campo, { target: { value: "1/1/2026 9:30" } });
  expect(campo).toHaveValue("1/1/2026 9:30");
  expect(screen.getByRole("status")).toHaveTextContent("2026-01-01T09:30");
  fireEvent.blur(campo);
  expect(campo).toHaveValue("01/01/2026 09:30");
});

it("clique em campo externo fecha sem cancelar o evento nem roubar seu foco", () => {
  const { abrir, aoMudar } = montar();
  render(<input aria-label="Outro campo" />);
  fireEvent.click(abrir);
  const outro = screen.getByLabelText("Outro campo");
  expect(fireEvent.pointerDown(outro)).toBe(true);
  act(() => outro.focus());
  fireEvent.pointerUp(outro);
  fireEvent.click(outro);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(outro).toHaveFocus();
  expect(aoMudar).not.toHaveBeenCalled();
});

it.each([
  ["2026-10-28T14:30", "Home", "domingo, 25 de outubro de 2026"],
  ["2026-10-28T14:30", "End", "sábado, 31 de outubro de 2026"],
  ["2026-10-28T14:30", "PageUp", "segunda-feira, 28 de setembro de 2026"],
  ["2026-10-28T14:30", "PageDown", "sábado, 28 de novembro de 2026"],
  ["2026-01-31T14:30", "PageDown", "sábado, 28 de fevereiro de 2026"],
  ["2026-03-31T14:30", "PageUp", "sábado, 28 de fevereiro de 2026"],
  ["2026-01-01T14:30", "Home", "domingo, 28 de dezembro de 2025"],
  ["2026-12-31T14:30", "End", "sábado, 2 de janeiro de 2027"],
])("navega de %s com %s", (valor, tecla, destino) => {
  const { abrir, aoMudar } = montar(valor);
  fireEvent.click(abrir);
  fireEvent.keyDown(document.activeElement!, { key: tecla });
  expect(screen.getByRole("button", { name: destino })).toHaveFocus();
  expect(screen.getByRole("dialog")).toBeInTheDocument();
  expect(aoMudar).not.toHaveBeenCalled();
});
