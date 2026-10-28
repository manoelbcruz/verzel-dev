import type { Resultado } from "../api/tipos";
import Dinheiro from "./Dinheiro";

export default function ResultadoLote({ resultado }: { resultado: Resultado | null }) {
  if (!resultado) return <p>Apurando resultado</p>;
  if (resultado.situacao === "sem_lances") return <p>Encerrado sem lances</p>;
  return (
    <p>
      Arrematado por <Dinheiro centavos={resultado.valor_centavos!} />
      {" · "}{resultado.vencedor_pseudonimo}
    </p>
  );
}
