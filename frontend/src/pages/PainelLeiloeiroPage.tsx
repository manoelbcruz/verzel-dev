import { Link } from "react-router";
import { usePainel } from "../api/consultas";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import { useRefetchNosLimites } from "../hooks/useRefetchNosLimites";
import { faseEfetiva } from "../lib/fase";
import { formatarDataHora } from "../lib/datas";
import Carregando from "../components/Carregando";
import CancelarLote from "../components/CancelarLote";
import Dinheiro from "../components/Dinheiro";
import MensagemErro from "../components/MensagemErro";
import ResultadoLote from "../components/ResultadoLote";
import SeloFase from "../components/SeloFase";

export default function PainelLeiloeiroPage() {
  const consulta = usePainel();
  const agora = useAgoraServidor();
  const lotes = consulta.data?.lotes ?? [];
  useRefetchNosLimites(consulta.refetch, lotes.flatMap((lote) => [lote.inicio_em, lote.fim_em]));

  return (
    <>
      <h1>Painel do leiloeiro</h1>
      <Link className="botao" to="/painel/novo">Novo lote</Link>
      <MensagemErro erro={consulta.error} />
      {consulta.isPending && <Carregando />}
      {consulta.data && (
        <section className="secao painel">
          <h2>Total recebido</h2>
          <p className="valor-destaque">
            <Dinheiro centavos={consulta.data.total_recebido_centavos} />
          </p>
        </section>
      )}
      <h2>Meus lotes</h2>
      {!consulta.isPending && !lotes.length && <p>Você ainda não publicou lotes.</p>}
      <ul className="lista">
        {lotes.map((lote) => {
          const fase = faseEfetiva(lote, agora);
          return (
            <li key={lote.id}>
              <h3><Link to={`/lotes/${lote.id}`}>{lote.titulo}</Link></h3>
              <SeloFase fase={fase} />
              <p>
                Início: {formatarDataHora(lote.inicio_em)} · Fim: {formatarDataHora(lote.fim_em)}
              </p>
              <p>
                Lance atual: <Dinheiro
                  centavos={lote.lance_atual_centavos ?? lote.lance_inicial_centavos}
                /> · {lote.total_lances} {lote.total_lances === 1 ? "lance" : "lances"}
              </p>
              <p>
                Valor mínimo (lance inicial): <Dinheiro centavos={lote.lance_inicial_centavos} />
              </p>
              {fase === "encerrado" && <ResultadoLote resultado={lote.resultado} />}
              {lote.resultado?.comprovante_codigo && (
                <Link
                  aria-label={`Ver comprovante: ${lote.titulo}`}
                  to={`/comprovantes/${lote.resultado.comprovante_codigo}`}
                >
                  Ver comprovante
                </Link>
              )}
              {lote.cancelavel && fase !== "encerrado" && (
                <CancelarLote id={lote.id} titulo={lote.titulo} />
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
