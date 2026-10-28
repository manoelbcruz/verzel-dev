import { useEffect, useState } from "react";
import { useTempoReal } from "../tempoReal/TempoRealProvider";

export default function IndicadorConexao() {
  const { conectado } = useTempoReal();
  const [demorado, setDemorado] = useState(false);
  useEffect(() => {
    if (conectado) {
      setDemorado(false);
      return;
    }
    const timer = setTimeout(() => setDemorado(true), 5000);
    return () => clearTimeout(timer);
  }, [conectado]);
  let texto = "Conectando ao tempo real";
  if (conectado) texto = "● Tempo real ativo";
  else if (demorado) texto = "Reconectando, atualizando a cada poucos segundos";
  return <small role="status" className="conexao">{texto}</small>;
}
