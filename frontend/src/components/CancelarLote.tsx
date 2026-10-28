import { useState } from "react";
import { useCancelar } from "../api/mutacoes";
import MensagemErro from "./MensagemErro";

export default function CancelarLote({ id, titulo }: { id: string; titulo: string }) {
  const [confirmar, setConfirmar] = useState(false);
  const comando = useCancelar();
  return (
    <div>
      {!confirmar ? (
        <button aria-label={`Cancelar lote: ${titulo}`} onClick={() => setConfirmar(true)}>
          Cancelar lote
        </button>
      ) : (
        <div>
          <p>Cancelar este lote sem lances?</p>
          <button disabled={comando.estado === "enviando"} onClick={() => void comando.enviar(id)}>
            Confirmar cancelamento
          </button>{" "}
          <button onClick={() => setConfirmar(false)}>Manter lote</button>
        </div>
      )}
      <MensagemErro erro={comando.erro} />
    </div>
  );
}
