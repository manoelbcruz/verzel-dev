import { screen } from "@testing-library/react";
import { ANA, LEILOEIRO, lote } from "../test/dados";
import { renderizar } from "../test/utilitarios";
import PainelPosicao from "./PainelPosicao";
import type { Fase, LoteDetalhe, Usuario } from "../api/tipos";

const participacao = {
  meu_pseudonimo: "Pessoa-A", ganhando: true, meu_maior_lance_centavos: 1600,
  posicao: 1, total_participantes: 3,
};
const resultado = {
  situacao: "arrematado" as const, valor_centavos: 1600, vencedor_pseudonimo: "Pessoa-A",
  encerrado_em: new Date().toISOString(), comprovante_codigo: "comprovante-A",
};
it.each<[Usuario | null, Partial<LoteDetalhe>, Fase, string]>([
  [null, {}, "ao_vivo", "Entre como licitante para dar lances"],
  [LEILOEIRO, {}, "ao_vivo", "Leiloeiros não dão lances"],
  [ANA, {}, "ao_vivo", "Você ainda não deu lance neste lote"],
  [ANA, { minha_participacao: participacao }, "ao_vivo", "Você está ganhando"],
  [
    ANA, { minha_participacao: { ...participacao, ganhando: false, posicao: 2 } },
    "ao_vivo", "Você foi superado",
  ],
  [ANA, { minha_participacao: participacao, resultado }, "encerrado", "Você arrematou este lote"],
  [
    ANA, { minha_participacao: { ...participacao, meu_pseudonimo: "Pessoa-B" }, resultado },
    "encerrado", "Você não arrematou este lote",
  ],
])("mostra posição %s %s %s", (usuario, dados, fase, texto) => {
  renderizar(<PainelPosicao lote={lote(dados)} usuario={usuario} fase={fase} />);
  expect(screen.getByRole("status")).toHaveTextContent(texto);
  if (texto === "Você foi superado") {
    expect(screen.getByRole("status")).toHaveTextContent("2º de 3 participantes");
  }
  if (texto === "Você está ganhando") {
    expect(screen.getByRole("status")).toHaveTextContent("R$ 16,00");
  }
  expect(!!screen.queryByRole("link", { name: "Ver comprovante" }))
    .toBe(texto === "Você arrematou este lote");
});
