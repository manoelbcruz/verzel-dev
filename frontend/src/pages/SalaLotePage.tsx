import { Link, useParams } from "react-router";
import { useLote, useSessao } from "../api/consultas";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import { useRefetchNosLimites } from "../hooks/useRefetchNosLimites";
import { faseEfetiva } from "../lib/fase";
import Carregando from "../components/Carregando";
import MensagemErro from "../components/MensagemErro";
import ListaAtributos from "../components/ListaAtributos";
import SeloFase from "../components/SeloFase";
import ContagemRegressiva from "../components/ContagemRegressiva";
import Dica from "../components/Dica";
import Dinheiro from "../components/Dinheiro";
import PainelPosicao from "../components/PainelPosicao";
import FormularioLance from "../components/FormularioLance";
import HistoricoLances from "../components/HistoricoLances";
import AvisoProrrogacao from "../components/AvisoProrrogacao";
import ResultadoLote from "../components/ResultadoLote";
import CancelarLote from "../components/CancelarLote";

export default function SalaLotePage() {
  const { loteId = "" } = useParams();
  const consulta = useLote(loteId);
  const sessao = useSessao();
  const agora = useAgoraServidor();
  const lote = consulta.data;
  useRefetchNosLimites(consulta.refetch, [lote?.inicio_em, lote?.fim_em]);
  if (!lote) return consulta.error ? <MensagemErro erro={consulta.error} porId /> : <Carregando />;
  const fase = faseEfetiva(lote, agora);

  return (
    <>
      <Link to="/">← Vitrine</Link>
      <h1>{lote.titulo}</h1>
      <div className="sala">
        <section>
          <img className="obra" src={lote.imagem_url} alt={lote.titulo} />
          <ListaAtributos atributos={lote.atributos} />
        </section>
        <section className="painel">
          <SeloFase fase={fase} />
          {fase === "cancelado" ? (
            <p role="status">Lote cancelado</p>
          ) : fase === "encerrado" ? (
            <div role="status"><ResultadoLote resultado={lote.resultado} /></div>
          ) : (
            <p>
              {fase === "agendado" ? "Começa em" : "Termina em"}{" "}
              <ContagemRegressiva
                alvo={fase === "agendado" ? lote.inicio_em : lote.fim_em}
                inicio={fase === "agendado"}
              />
            </p>
          )}
          <p>{lote.total_lances ? "Lance atual" : "Lance inicial"}</p>
          <p className="valor-destaque">
            <Dinheiro centavos={lote.lance_atual_centavos ?? lote.lance_inicial_centavos} />
          </p>
          {(fase === "agendado" || fase === "ao_vivo") && (
            <p>Próximo mínimo: <Dinheiro centavos={lote.proximo_lance_minimo_centavos} /></p>
          )}
          <p>
            {lote.total_lances} {lote.total_lances === 1 ? "lance" : "lances"}{" "}
            {lote.lider_pseudonimo && (
              <>· Líder: <Dica texto={lote.lider_pseudonimo} focavel={false} resumo>
                {lote.lider_pseudonimo.slice(0, 6)}
              </Dica></>
            )}
          </p>
          <AvisoProrrogacao loteId={lote.id} fimEm={lote.fim_em} />
          <PainelPosicao lote={lote} usuario={sessao.data ?? null} fase={fase} />
          <FormularioLance lote={lote} usuario={sessao.data ?? null} fase={fase} />
          <MensagemErro erro={consulta.error} />
          <div className="acoes">
            <Link to={`/auditoria/${lote.id}`}>Ver auditoria</Link>
            {lote.resultado?.comprovante_codigo && (
              <Link to={`/comprovantes/${lote.resultado.comprovante_codigo}`}>Ver comprovante</Link>
            )}
          </div>
          {lote.cancelavel && <CancelarLote id={lote.id} titulo={lote.titulo} />}
        </section>
      </div>
      <HistoricoLances
        lances={lote.lances}
        meuPseudonimo={lote.minha_participacao?.meu_pseudonimo}
      />
    </>
  );
}
