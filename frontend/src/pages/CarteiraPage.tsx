import { useState } from "react";
import { Link } from "react-router";
import { useCarteira, usePainel, useParticipacoes, useSessao } from "../api/consultas";
import { useDepositar } from "../api/mutacoes";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import { useRefetchNosLimites } from "../hooks/useRefetchNosLimites";
import { faseEfetiva } from "../lib/fase";
import { formatarCentavos, MAX_DEPOSITO, parseReais } from "../lib/dinheiro";
import { formatarDataHora } from "../lib/datas";
import CampoReais from "../components/CampoReais";
import Carregando from "../components/Carregando";
import Dinheiro from "../components/Dinheiro";
import MensagemErro from "../components/MensagemErro";
import SeloFase from "../components/SeloFase";

const TIPOS = {
  deposito: "Depósito",
  arremate_debito: "Pagamento de arremate",
  arremate_credito: "Recebimento de arremate",
};

export default function CarteiraPage() {
  const consulta = useCarteira();
  const sessao = useSessao();
  const deposito = useDepositar();
  const participacoes = useParticipacoes();
  const painel = usePainel();
  const agora = useAgoraServidor();
  const [texto, setTexto] = useState("100,00");
  const [erroCampo, setErroCampo] = useState<string>();
  // A carteira não traz datas. As consultas do próprio papel fornecem os limites dos lotes.
  const lotes = sessao.data?.papel === "licitante"
    ? participacoes.data?.map((p) => p.lote) ?? []
    : painel.data?.lotes ?? [];
  useRefetchNosLimites(consulta.refetch, lotes.flatMap((lote) => [lote.inicio_em, lote.fim_em]));
  if (!consulta.data) {
    return consulta.error ? <MensagemErro erro={consulta.error} /> : <Carregando />;
  }
  const carteira = consulta.data;

  return (
    <>
      <h1>Minha carteira</h1>
      <div className="grade">
        <section className="painel">
          <h2>Saldo total</h2><Dinheiro centavos={carteira.saldo_total_centavos} />
        </section>
        <section className="painel">
          <h2>Comprometido</h2><Dinheiro centavos={carteira.comprometido_centavos} />
          <p>Reservado nos lotes em que você lidera.</p>
        </section>
        <section className="painel">
          <h2>Disponível</h2><Dinheiro centavos={carteira.disponivel_centavos} />
        </section>
      </div>
      <MensagemErro erro={consulta.error || participacoes.error || painel.error} />
      {sessao.data?.papel === "licitante" && (
        <section className="secao painel">
          <h2>Depositar saldo simulado</h2>
          <form noValidate onSubmit={(e) => {
            e.preventDefault();
            const valor = parseReais(texto, { maximo: MAX_DEPOSITO });
            if (!valor.ok) {
              setErroCampo(valor.erro);
              e.currentTarget.querySelector("input")?.focus();
              return;
            }
            setErroCampo(undefined);
            void deposito.enviar(valor.centavos);
          }}>
            <CampoReais
              rotulo="Valor do depósito (R$)"
              valor={texto}
              mudar={setTexto}
              erro={erroCampo}
              disabled={deposito.estado === "enviando"}
            />
            <div className="acoes">
              {[10000, 50000, 100000].map((valor) => (
                <button
                  type="button"
                  key={valor}
                  onClick={() => setTexto(formatarCentavos(valor).replace(/^R\$\s*/, ""))}
                >
                  {formatarCentavos(valor)}
                </button>
              ))}
              <button className="primario" disabled={deposito.estado === "enviando"}>
                Depositar
              </button>
            </div>
            <MensagemErro erro={deposito.erro} contexto={{ operacao: "deposito" }} />
            {deposito.estado === "incerto" && (
              <button type="button" onClick={() => void deposito.repetir()}>Tentar de novo</button>
            )}
            {deposito.estado === "aceito" && (
              <p role="status">Depósito registrado. Consultando saldo atualizado.</p>
            )}
          </form>
        </section>
      )}
      <section className="secao">
        <h2>Reservas</h2>
        {!carteira.reservas.length && <p>Você não tem saldo reservado.</p>}
        <ul className="lista">
          {carteira.reservas.map((reserva) => {
            const lote = lotes.find((item) => item.id === reserva.lote_id);
            return (
              <li key={reserva.lote_id}>
                <Link to={`/lotes/${reserva.lote_id}`}>{reserva.titulo}</Link>
                {" · "}<Dinheiro centavos={reserva.valor_centavos} />{" "}
                {lote && <SeloFase fase={faseEfetiva(lote, agora)} />}
              </li>
            );
          })}
        </ul>
      </section>
      <section className="secao">
        <h2>Lançamentos</h2>
        {!carteira.lancamentos.length && <p>Ainda não há lançamentos.</p>}
        <ul className="lista">
          {carteira.lancamentos.map((lancamento, i) => (
            <li key={i}>
              <strong>{TIPOS[lancamento.tipo]}</strong>
              {" · "}<Dinheiro centavos={lancamento.valor_centavos} />
              <p>
                {formatarDataHora(lancamento.criado_em)}{" "}
                {lancamento.lote_id && <Link to={`/lotes/${lancamento.lote_id}`}>Ver lote</Link>}
              </p>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
