import { useContagemRegressiva } from "../hooks/useContagemRegressiva";
import { formatarDuracaoFalada } from "../lib/datas";

export default function ContagemRegressiva({ alvo, inicio = false }: {
  alvo: string;
  inicio?: boolean;
}) {
  const { restanteMs, texto, vencido, urgente } = useContagemRegressiva(alvo);
  return (
    <span role="timer" aria-label={formatarDuracaoFalada(restanteMs)}>
      <time dateTime={alvo} data-urgente={urgente} className="contagem">
        {vencido
          ? (inicio ? "Iniciando…" : "Encerrando…")
          : texto}
      </time>
    </span>
  );
}
