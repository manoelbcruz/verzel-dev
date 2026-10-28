import { screen } from "@testing-library/react";
import MeusArrematesPage from "./MeusArrematesPage";
import { ANA, lote } from "../test/dados";
import { renderizar, simularApi } from "../test/utilitarios";

it("agrupa disputas, apuração, vitória e derrota e oferece comprovante", async () => {
  simularApi({
    "GET /api/me/participacoes": [
      "ganhando", "aguardando_resultado", "arrematado", "nao_arrematado",
    ].map((situacao, i) => ({
      lote: lote({
        id: `lote-${i}`,
        titulo: `Obra ${i}`,
        fim_em: new Date(Date.now() + (i ? -1000 : 600000)).toISOString(),
      }),
      meu_pseudonimo: "Pessoa",
      meu_maior_lance_centavos: 1500,
      situacao,
      comprovante_codigo: situacao === "arrematado" ? "meu-comprovante" : null,
    })),
  });
  renderizar(<MeusArrematesPage />, { usuario: ANA });
  expect(await screen.findByRole("link", { name: /Ver comprovante:/ }))
    .toHaveAttribute("href", "/comprovantes/meu-comprovante");
  for (const grupo of [
    "Disputando agora", "Apurando resultado", "Arrematados", "Não arrematados",
  ]) {
    expect(screen.getByRole("heading", { name: grupo })).toBeInTheDocument();
  }
  expect(screen.getByRole("button", { name: /Copiar link:/ })).toBeInTheDocument();
});
