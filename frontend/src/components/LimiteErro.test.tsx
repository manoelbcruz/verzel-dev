import { screen } from "@testing-library/react";
import { renderizar } from "../test/utilitarios";
import Layout from "./Layout";

it("mantém navegação e oferece retorno à vitrine depois de erro na rota", () => {
  const log = vi.spyOn(console, "error").mockImplementation(() => {});
  function Quebrada() {
    throw new Error("Dado inválido");
    return null;
  }
  try {
    renderizar(<Layout><Quebrada /></Layout>);
    expect(screen.getByRole("alert")).toHaveTextContent("Não foi possível exibir esta página");
    expect(screen.getByRole("link", { name: "Voltar à vitrine" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  } finally { log.mockRestore(); }
});
