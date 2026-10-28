import { Link, useParams } from "react-router";
import { useComprovante } from "../api/consultas";
import { formatarDataHora } from "../lib/datas";
import Carregando from "../components/Carregando";
import CompartilharLink from "../components/CompartilharLink";
import Dinheiro from "../components/Dinheiro";
import ListaAtributos from "../components/ListaAtributos";
import MensagemErro from "../components/MensagemErro";

export default function ComprovantePage() {
  const { codigo = "" } = useParams();
  const consulta = useComprovante(codigo);
  const comprovante = consulta.data;
  if (!comprovante) {
    return consulta.error ? <MensagemErro erro={consulta.error} porId /> : <Carregando />;
  }

  return (
    <>
      <p className="sobretitulo">COMPROVANTE PÚBLICO DE ARREMATE</p>
      <h1>{comprovante.titulo}</h1>
      <div className="sala">
        <div>
          <img className="obra" src={comprovante.imagem_url} alt={comprovante.titulo} />
          <ListaAtributos atributos={comprovante.atributos} />
        </div>
        <section className="painel">
          <h2>Arremate concluído</h2>
          <p className="valor-destaque"><Dinheiro centavos={comprovante.valor_centavos} /></p>
          <p>Vencedor: {comprovante.vencedor_pseudonimo}</p>
          <p>Encerrado em {formatarDataHora(comprovante.encerrado_em)}</p>
          <p>Evento de encerramento: sequência {comprovante.evento_encerramento.seq}</p>
          <p className="mac">{comprovante.evento_encerramento.mac}</p>
          <div className="acoes">
            <Link to={`/auditoria/${comprovante.lote_id}`}>Ver auditoria</Link>
            <Link to={`/lotes/${comprovante.lote_id}`}>Ver sala do lote</Link>
          </div>
          <CompartilharLink caminho={`/comprovantes/${comprovante.codigo}`} />
        </section>
      </div>
    </>
  );
}
