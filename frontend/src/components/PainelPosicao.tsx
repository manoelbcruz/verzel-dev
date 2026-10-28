import { Link } from "react-router";
import type { Fase, LoteDetalhe, Usuario } from "../api/tipos";
import Dinheiro from "./Dinheiro";

export default function PainelPosicao({ lote, usuario, fase }: {
  lote: LoteDetalhe;
  usuario: Usuario | null;
  fase: Fase;
}) {
  const minha = lote.minha_participacao;
  const aberto = fase === "agendado" || fase === "ao_vivo";
  const venceu = lote.resultado?.situacao === "arrematado"
    && minha?.meu_pseudonimo === lote.resultado.vencedor_pseudonimo;
  let conteudo;
  let classe = "posicao";
  if (!usuario) {
    if (!aberto) return null;
    conteudo = (
      <Link to={`/entrar?volta=${encodeURIComponent(`/lotes/${lote.id}`)}`}>
        Entre como licitante para dar lances
      </Link>
    );
  } else if (usuario.papel === "leiloeiro") {
    conteudo = "Leiloeiros não dão lances";
  } else if (fase === "encerrado" && lote.resultado) {
    conteudo = <>
      {venceu ? "Você arrematou este lote" : "Você não arrematou este lote"}
      {venceu && lote.resultado.comprovante_codigo && (
        <p><Link to={`/comprovantes/${lote.resultado.comprovante_codigo}`}>
          Ver comprovante
        </Link></p>
      )}
    </>;
  } else if (!minha) {
    conteudo = "Você ainda não deu lance neste lote";
  } else {
    classe += minha.ganhando ? " posicao-ganhando" : " posicao-superado";
    conteudo = <>
      <span aria-hidden="true">{minha.ganhando ? "✓" : "⚠"} </span>
      <strong>{minha.ganhando ? "Você está ganhando" : "Você foi superado"}</strong>
      <p>Seu maior lance: <Dinheiro centavos={minha.meu_maior_lance_centavos} /></p>
      <p>
        {minha.posicao}º de {minha.total_participantes}{" "}
        {minha.total_participantes === 1 ? "participante" : "participantes"}
      </p>
    </>;
  }
  return <div role="status" aria-live="polite" className={classe}>{conteudo}</div>;
}
