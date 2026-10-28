import { useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { ReactNode } from "react";

// `resumo`: o conteúdo é uma abreviação do texto, então o leitor de tela recebe o texto completo
// no lugar dela. Sem `resumo` (por exemplo, em volta de um botão), o conteúdo fica como está.
export default function Dica({ texto, children, focavel = true, resumo = false }: {
  texto: string;
  children: ReactNode;
  focavel?: boolean;
  resumo?: boolean;
}) {
  const id = useId();
  const gatilho = useRef<HTMLSpanElement>(null);
  const balao = useRef<HTMLSpanElement>(null);
  const [posicao, setPosicao] = useState({ left: 0, top: 0 });
  const [foco, setFoco] = useState(false);
  const [sobre, setSobre] = useState(false);
  const [oculta, setOculta] = useState(false);
  const aberta = (foco || sobre) && !oculta;
  useLayoutEffect(() => {
    if (!aberta) return;
    function posicionar() {
      const origem = gatilho.current?.getBoundingClientRect();
      const dica = balao.current?.getBoundingClientRect();
      if (!origem || !dica) return;
      setPosicao({
        left: Math.max(8, Math.min(origem.left, window.innerWidth - dica.width - 8)),
        top: origem.bottom + dica.height <= window.innerHeight - 8
          ? origem.bottom : Math.max(8, origem.top - dica.height),
      });
    }
    posicionar();
    window.addEventListener("resize", posicionar);
    window.addEventListener("scroll", posicionar, true);
    return () => {
      window.removeEventListener("resize", posicionar);
      window.removeEventListener("scroll", posicionar, true);
    };
  }, [aberta]);
  return (
    <span
      ref={gatilho}
      className="dica"
      tabIndex={focavel ? 0 : undefined}
      aria-describedby={aberta ? id : undefined}
      onFocus={() => { if (focavel) { setFoco(true); setOculta(false); } }}
      onBlur={() => setFoco(false)}
      onMouseEnter={() => { setSobre(true); setOculta(false); }}
      onMouseLeave={() => setSobre(false)}
      onKeyDown={(e) => { if (e.key === "Escape") setOculta(true); }}
    >
      {!resumo ? children : (
        <>
          <span aria-hidden="true">{children}</span>
          <span className="visualmente-oculto">{texto}</span>
        </>
      )}
      {aberta && createPortal(
        <span ref={balao} id={id} role="tooltip" className="dica-balao" style={posicao}>
          {texto}
        </span>, document.body,
      )}
    </span>
  );
}
