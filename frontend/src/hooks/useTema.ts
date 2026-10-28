import { useEffect, useState } from "react";
import { aplicarTema, lerTema, salvarTema } from "../lib/tema";
import type { Tema } from "../lib/tema";

export function useTema() {
  const [tema, setTema] = useState(lerTema);
  useEffect(() => {
    const sistema = matchMedia("(prefers-color-scheme: dark)");
    const aplicar = () => aplicarTema(tema);
    aplicar();
    sistema.addEventListener("change", aplicar);
    return () => sistema.removeEventListener("change", aplicar);
  }, [tema]);
  return {
    tema,
    escolher: (novo: Tema) => {
      salvarTema(novo);
      setTema(novo);
    },
  };
}
