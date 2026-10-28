import { useState } from "react";

export default function CompartilharLink({ caminho, titulo }: {
  caminho: string;
  titulo?: string;
}) {
  const [manual, setManual] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const url = location.origin + caminho;
  async function copiar() {
    try {
      if (!navigator.clipboard) {
        setManual(true);
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopiado(true);
    } catch {
      setManual(true);
    }
  }
  return (
    <div>
      <button
        aria-label={titulo ? `Copiar link: ${titulo}` : undefined}
        onClick={() => void copiar()}
      >
        Copiar link
      </button>
      {copiado && <span role="status"> Link copiado.</span>}
      {manual && (
        <label>
          Link para compartilhar
          <input readOnly value={url} onFocus={(e) => e.target.select()} />
        </label>
      )}
    </div>
  );
}
