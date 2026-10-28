import { Link } from "react-router";
import { useParticipacoes } from "../api/consultas";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import { useRefetchNosLimites } from "../hooks/useRefetchNosLimites";
import { faseEfetiva } from "../lib/fase";
import type { Participacao } from "../api/tipos";
import Carregando from "../components/Carregando";
import CartaoLote from "../components/CartaoLote";
import CompartilharLink from "../components/CompartilharLink";
import Dinheiro from "../components/Dinheiro";
import MensagemErro from "../components/MensagemErro";

export default function MeusArrematesPage() {
  const consulta = useParticipacoes();
  const agora = useAgoraServidor();
  const participacoes = consulta.data ?? [];
  useRefetchNosLimites(
    consulta.refetch,
    participacoes.flatMap((p) => [p.lote.inicio_em, p.lote.fim_em]),
  );
  function grupo(p: Participacao) {
    if (p.situacao === "arrematado") return "Arrematados";
    if (p.situacao === "nao_arrematado") return "Não arrematados";
    return faseEfetiva(p.lote, agora) === "encerrado" ? "Apurando resultado" : "Disputando agora";
  }

  return (
    <>
      <h1>Meus arremates</h1>
      <MensagemErro erro={consulta.error} />
      {consulta.isPending && <Carregando />}
      {["Disputando agora", "Apurando resultado", "Arrematados", "Não arrematados"].map((nome) => {
        const itens = participacoes.filter((p) => grupo(p) === nome);
        return (
          <section className="secao" key={nome}>
            <h2>{nome}</h2>
            {!itens.length && <p>Nenhum lote neste grupo.</p>}
            <div className="grade">
              {itens.map((p) => (
                <div key={p.lote.id}>
                  <CartaoLote lote={p.lote} />
                  {nome === "Disputando agora" && (
                    <p role="status">
                      {p.situacao === "ganhando" ? "Você está ganhando" : "Você foi superado"}
                    </p>
                  )}
                  <p>Seu maior lance: <Dinheiro centavos={p.meu_maior_lance_centavos} /></p>
                  {p.comprovante_codigo && (
                    <>
                      <Link
                        aria-label={`Ver comprovante: ${p.lote.titulo}`}
                        to={`/comprovantes/${p.comprovante_codigo}`}
                      >
                        Ver comprovante
                      </Link>
                      <CompartilharLink
                        titulo={p.lote.titulo}
                        caminho={`/comprovantes/${p.comprovante_codigo}`}
                      />
                    </>
                  )}
                </div>
              ))}
            </div>
          </section>
        );
      })}
    </>
  );
}
