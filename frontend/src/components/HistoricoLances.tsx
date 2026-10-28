import type { LanceHistorico } from "../api/tipos";
import { formatarDataHora } from "../lib/datas";
import Dica from "./Dica";
import Dinheiro from "./Dinheiro";

export default function HistoricoLances({ lances, meuPseudonimo }: {
  lances: LanceHistorico[];
  meuPseudonimo?: string;
}) {
  return (
    <section>
      <h2>Histórico de lances</h2>
      {!lances.length && <p>Ainda não há lances.</p>}
      <ol className="lista">
        {[...lances].reverse().map((lance) => (
          <li key={lance.seq}>
            <strong>
              <Dica texto={lance.pseudonimo} focavel={false} resumo>
                {lance.pseudonimo.slice(0, 6)}
              </Dica>
              {lance.pseudonimo === meuPseudonimo ? " (você)" : ""}
            </strong>{" "}
            · <Dinheiro centavos={lance.valor_centavos} />
            <p>
              {formatarDataHora(lance.instante)}{" "}
              {lance.prorrogou && <span className="selo">prorrogou</span>}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}
