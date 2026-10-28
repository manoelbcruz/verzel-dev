import { Link, useParams } from "react-router";
import { useAuditoria } from "../api/consultas";
import { formatarDataHora } from "../lib/datas";
import Carregando from "../components/Carregando";
import Dica from "../components/Dica";
import Dinheiro from "../components/Dinheiro";
import MensagemErro from "../components/MensagemErro";

const TIPOS: Record<string, string> = {
  publicacao: "Publicação",
  lance: "Lance",
  cancelamento: "Cancelamento",
  encerramento: "Encerramento",
};

export default function AuditoriaPage() {
  const { loteId = "" } = useParams();
  const consulta = useAuditoria(loteId);
  const auditoria = consulta.data;
  if (!auditoria) {
    return consulta.error ? <MensagemErro erro={consulta.error} porId /> : <Carregando />;
  }

  return (
    <>
      <Link to={`/lotes/${auditoria.lote_id}`}>← Sala do lote</Link>
      <h1>Auditoria · {auditoria.titulo}</h1>
      <div className="painel" role="status">
        <h2>{auditoria.veredito === "integro" ? "✓ Íntegro" : "⚠ Adulterado"}</h2>
        {auditoria.falha && (
          <p>
            {auditoria.falha.codigo}: {auditoria.falha.mensagem}
            {auditoria.falha.seq !== null && ` · Sequência ${auditoria.falha.seq}`}
          </p>
        )}
        <p>{auditoria.eventos_verificados} de {auditoria.total_eventos} eventos verificados</p>
        <p>Método: {auditoria.metodo}</p>
        <p>Verificado em {formatarDataHora(auditoria.verificado_em)}</p>
      </div>
      <button disabled={consulta.isFetching} onClick={() => void consulta.refetch()}>
        Verificar novamente
      </button>
      <MensagemErro erro={consulta.error} />
      <p>
        A cadeia HMAC autentica os eventos de cada lote e sua ordem. A restauração de um estado
        antigo inteiro e autenticado não é detectada sem uma âncora externa.
      </p>
      <div className="tabela">
        <table>
          <thead>
            <tr>
              {[
                "Seq", "Tipo", "Instante", "Licitante", "Valor", "Novo fim", "Prorrogou",
                "MAC", "Verificado",
              ].map((rotulo) => <th key={rotulo} scope="col">{rotulo}</th>)}
            </tr>
          </thead>
          <tbody>
            {auditoria.eventos.map((evento) => (
              <tr key={evento.seq}>
                <td>{evento.seq}</td>
                <td>{TIPOS[evento.tipo] ?? evento.tipo}</td>
                <td>{formatarDataHora(evento.instante)}</td>
                <td>{evento.licitante_pseudonimo ?? "—"}</td>
                <td>
                  {evento.valor_centavos === null
                    ? "—"
                    : <Dinheiro centavos={evento.valor_centavos} />}
                </td>
                <td>{evento.fim_novo ? formatarDataHora(evento.fim_novo) : "—"}</td>
                <td>{evento.prorrogou ? "Sim" : "Não"}</td>
                <td><Dica texto={evento.mac}><code>{evento.mac.slice(0, 12)}…</code></Dica></td>
                <td>{evento.verificado ? "Sim" : "Não"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
