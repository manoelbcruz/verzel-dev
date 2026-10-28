import { useEffect, useRef, useState } from "react";
import { formatarDataHora } from "../lib/datas";
export default function AvisoProrrogacao({ loteId, fimEm }: { loteId: string; fimEm: string }) {
  const anterior = useRef({ loteId, fimEm });
  const [mostrar, setMostrar] = useState(false);
  useEffect(() => {
    const aumentou = anterior.current.loteId === loteId
      && Date.parse(fimEm) > Date.parse(anterior.current.fimEm);
    anterior.current = { loteId, fimEm };
    if (!aumentou) {
      setMostrar(false);
      return;
    }
    setMostrar(true);
    const timer = setTimeout(() => setMostrar(false), 10000);
    return () => clearTimeout(timer);
  }, [loteId, fimEm]);
  return mostrar ? (
    <p role="status" className="aviso">
      Prorrogado: o lote agora termina às {formatarDataHora(fimEm)}
    </p>
  ) : null;
}
