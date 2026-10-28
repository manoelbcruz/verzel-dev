import { Link } from "react-router";
import type { LoteResumo } from "../api/tipos";
import { faseEfetiva } from "../lib/fase";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import SeloFase from "./SeloFase";
import ContagemRegressiva from "./ContagemRegressiva";
import Dinheiro from "./Dinheiro";
import ResultadoLote from "./ResultadoLote";

export default function CartaoLote({ lote }: { lote: LoteResumo }) {
  const fase = faseEfetiva(lote, useAgoraServidor());
  return (
    <article className="cartao">
      <Link to={`/lotes/${lote.id}`}>
        <img src={lote.imagem_url} alt={lote.titulo} loading="lazy" />
        <h3>{lote.titulo}</h3>
      </Link>
      <SeloFase fase={fase} />
      {fase === "encerrado" ? (
        <ResultadoLote resultado={lote.resultado} />
      ) : (
        <>
          <p>
            {lote.total_lances ? "Lance atual" : "Lance inicial (sem lances)"}{" "}
            <strong>
              <Dinheiro centavos={lote.lance_atual_centavos ?? lote.lance_inicial_centavos} />
            </strong>
          </p>
          <p>{lote.total_lances} {lote.total_lances === 1 ? "lance" : "lances"}</p>
          {fase !== "cancelado" && (
            <p>
              {fase === "agendado" ? "Começa em" : "Termina em"}{" "}
              <ContagemRegressiva
                alvo={fase === "agendado" ? lote.inicio_em : lote.fim_em}
                inicio={fase === "agendado"}
              />
            </p>
          )}
        </>
      )}
    </article>
  );
}
