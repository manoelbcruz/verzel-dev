import { useEffect, useId, useRef, useState } from "react";
import {
  diasDoMes, formatarCampoDataHora, lerCampoDataHora, msParaDatetimeLocal,
} from "../lib/datas";
import { relogio } from "../lib/relogio";

const FORMATO = "Use o formato dd/mm/aaaa hh:mm";
const dois = (valor: number) => String(valor).padStart(2, "0");

function dataCivil(ano: number, mes: number, dia: number) {
  const data = new Date(0);
  data.setHours(12, 0, 0, 0);
  data.setFullYear(ano, mes - 1, dia);
  return data;
}

function diaInterno(data: Date) {
  return `${String(data.getFullYear()).padStart(4, "0")}-` +
    `${dois(data.getMonth() + 1)}-${dois(data.getDate())}`;
}

export default function CampoDataHora({
  rotulo, valor, aoMudar, desabilitado = false, invalido = false, descricaoId,
}: {
  rotulo: string;
  valor: string;
  aoMudar: (valor: string) => void;
  desabilitado?: boolean;
  invalido?: boolean;
  descricaoId?: string;
}) {
  const id = useId();
  const raiz = useRef<HTMLDivElement>(null);
  const campo = useRef<HTMLInputElement>(null);
  const botao = useRef<HTMLButtonElement>(null);
  const dias = useRef(new Map<string, HTMLButtonElement>());
  const focarDia = useRef(false);
  const valorDigitado = useRef<string | null>(null);
  const [texto, setTexto] = useState(() => formatarCampoDataHora(valor));
  const [erro, setErro] = useState(false);
  const [aberto, setAberto] = useState(false);
  const [mes, setMes] = useState(() => {
    const hoje = new Date(relogio.agora());
    return { ano: hoje.getFullYear(), numero: hoje.getMonth() + 1 };
  });
  const [dia, setDia] = useState("");
  const [foco, setFoco] = useState("");
  const [hora, setHora] = useState("00");
  const [minuto, setMinuto] = useState("00");
  const [erroHora, setErroHora] = useState(false);
  const horaRef = useRef<HTMLInputElement>(null);
  const minutoRef = useRef<HTMLInputElement>(null);
  const textoInvalido = texto !== "" && lerCampoDataHora(texto) === null;
  const horaValida = /^\d{1,2}$/.test(hora) && +hora <= 23;
  const minutoValido = /^\d{1,2}$/.test(minuto) && +minuto <= 59;

  useEffect(() => {
    if (valor !== valorDigitado.current) setTexto(formatarCampoDataHora(valor));
    valorDigitado.current = null;
    setErro(false);
  }, [valor]);
  useEffect(() => {
    campo.current?.setCustomValidity(textoInvalido ? FORMATO : "");
  }, [textoInvalido]);
  useEffect(() => {
    if (desabilitado) setAberto(false);
  }, [desabilitado]);
  useEffect(() => {
    if (aberto && focarDia.current) {
      dias.current.get(foco)?.focus();
      focarDia.current = false;
    }
  }, [aberto, foco, mes]);
  useEffect(() => {
    if (!aberto) return;
    const fecharFora = (e: PointerEvent) => {
      if (e.target instanceof Node && !raiz.current?.contains(e.target)) {
        setAberto(false);
        const focavel = e.target instanceof Element && e.target.closest(
          'input:not(:disabled), button:not(:disabled), select:not(:disabled), ' +
          'textarea:not(:disabled), a[href], [tabindex], [contenteditable="true"], label',
        );
        // Aguarda o foco padrão do clique antes de devolver ao botão.
        if (!focavel) setTimeout(() => botao.current?.focus(), 0);
      }
    };
    document.addEventListener("pointerdown", fecharFora);
    return () => document.removeEventListener("pointerdown", fecharFora);
  }, [aberto]);

  function fechar() {
    setAberto(false);
    botao.current?.focus();
  }

  function abrir() {
    const atual = valor || msParaDatetimeLocal(relogio.agora());
    const [ano, numero] = atual.slice(0, 10).split("-").map(Number);
    setMes({ ano, numero });
    setDia(atual.slice(0, 10));
    setFoco(atual.slice(0, 10));
    setHora(atual.slice(11, 13));
    setMinuto(atual.slice(14, 16));
    setErroHora(false);
    focarDia.current = true;
    setAberto(true);
  }

  function mudarMes(passo: number) {
    const data = dataCivil(mes.ano, mes.numero + passo, 1);
    setMes({ ano: data.getFullYear(), numero: data.getMonth() + 1 });
    setFoco(diaInterno(data));
  }

  function aplicar() {
    if (!horaValida || !minutoValido) {
      setErroHora(true);
      (horaValida ? minutoRef : horaRef).current?.focus();
      return;
    }
    const novo = `${dia}T${dois(+hora)}:${dois(+minuto)}`;
    setTexto(formatarCampoDataHora(novo));
    setErro(false);
    aoMudar(novo);
    fechar();
  }

  const hoje = msParaDatetimeLocal(relogio.agora()).slice(0, 10);
  const primeiro = dataCivil(mes.ano, mes.numero, 1);
  const descricao = [descricaoId, erro && textoInvalido ? `${id}-erro` : ""]
    .filter(Boolean).join(" ") || undefined;

  return (
    <div className="campo campo-data-hora" ref={raiz} onKeyDown={(e) => {
      if (aberto && e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        fechar();
      }
    }} onBlur={(e) => {
      // Sem relatedTarget o foco foi para o body (clique em área vazia do painel ou navegador que
      // não foca botão no clique); o clique fora já é tratado pelo pointerdown.
      if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) setAberto(false);
    }}>
      <label htmlFor={id}>{rotulo}</label>
      <div className="data-entrada">
        <input
          id={id}
          ref={campo}
          type="text"
          inputMode="numeric"
          placeholder="dd/mm/aaaa hh:mm"
          value={texto}
          disabled={desabilitado}
          aria-invalid={invalido || (erro && textoInvalido)}
          aria-describedby={descricao}
          onChange={(e) => {
            const novo = e.target.value;
            setTexto(novo);
            setErro(false);
            const interno = lerCampoDataHora(novo);
            if (!novo || interno) {
              valorDigitado.current = interno ?? "";
              aoMudar(valorDigitado.current);
            }
          }}
          onBlur={() => {
            setErro(true);
            const interno = lerCampoDataHora(texto);
            if (interno) setTexto(formatarCampoDataHora(interno));
          }}
          onInvalid={(e) => { e.preventDefault(); setErro(true); }}
        />
        <button
          ref={botao}
          type="button"
          disabled={desabilitado}
          aria-label={`Abrir calendário de ${rotulo}`}
          aria-haspopup="dialog"
          aria-expanded={aberto}
          aria-controls={aberto ? `${id}-calendario` : undefined}
          onClick={() => aberto ? fechar() : abrir()}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"
            stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 5h16v16H4ZM4 10h16M8 3v4m8-4v4" />
          </svg>
        </button>
      </div>
      {erro && textoInvalido && <span id={`${id}-erro`} className="erro">{FORMATO}</span>}
      {aberto && (
        <div id={`${id}-calendario`} className="calendario" role="dialog"
          aria-label={`Escolher ${rotulo}`}>
          <div className="calendario-cabecalho">
            <button type="button" aria-label="Mês anterior" onClick={() => mudarMes(-1)}
              disabled={mes.ano === 1 && mes.numero === 1}>←</button>
            <span aria-live="polite">
              {primeiro.toLocaleDateString("pt-BR", { month: "long", year: "numeric" })}
            </span>
            <button type="button" aria-label="Mês seguinte" onClick={() => mudarMes(1)}
              disabled={mes.ano === 9999 && mes.numero === 12}>→</button>
          </div>
          <div className="calendario-dias" role="group" aria-label="Dias do mês">
            {["dom", "seg", "ter", "qua", "qui", "sex", "sáb"].map((nome) => (
              <span key={nome} aria-hidden="true">{nome}</span>
            ))}
            {Array.from({ length: primeiro.getDay() }, (_, i) => (
              <span key={`vazio-${i}`} aria-hidden="true" />
            ))}
            {Array.from({ length: diasDoMes(mes.ano, mes.numero) }, (_, i) => {
              const data = dataCivil(mes.ano, mes.numero, i + 1);
              const chave = diaInterno(data);
              return (
                <button
                  key={chave}
                  ref={(elemento) => {
                    if (elemento) dias.current.set(chave, elemento);
                    else dias.current.delete(chave);
                  }}
                  type="button"
                  tabIndex={foco === chave ? 0 : -1}
                  aria-label={data.toLocaleDateString("pt-BR", { dateStyle: "full" })}
                  aria-pressed={dia === chave}
                  aria-current={hoje === chave ? "date" : undefined}
                  onFocus={() => setFoco(chave)}
                  onClick={() => setDia(chave)}
                  onKeyDown={(e) => {
                    const passos: Record<string, number> = {
                      ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7,
                      Home: -data.getDay(), End: 6 - data.getDay(),
                    };
                    const pagina = e.key === "PageUp" ? -1 : e.key === "PageDown" ? 1 : 0;
                    if (!(e.key in passos) && !pagina) return;
                    e.preventDefault();
                    const proximo = pagina
                      ? dataCivil(mes.ano, mes.numero + pagina, 1)
                      : dataCivil(mes.ano, mes.numero, i + 1 + passos[e.key]);
                    if (pagina) proximo.setDate(Math.min(i + 1,
                      diasDoMes(proximo.getFullYear(), proximo.getMonth() + 1)));
                    if (proximo.getFullYear() < 1 || proximo.getFullYear() > 9999) return;
                    focarDia.current = true;
                    setMes({ ano: proximo.getFullYear(), numero: proximo.getMonth() + 1 });
                    setFoco(diaInterno(proximo));
                  }}
                >{i + 1}</button>
              );
            })}
          </div>
          <div className="calendario-hora">
            {[
              { rotulo: "Hora", texto: hora, mudar: setHora, ref: horaRef, valida: horaValida },
              { rotulo: "Minuto", texto: minuto, mudar: setMinuto,
                ref: minutoRef, valida: minutoValido },
            ].map((parte) => (
              <label key={parte.rotulo}>
                {parte.rotulo}
                <input type="text" inputMode="numeric" value={parte.texto} ref={parte.ref}
                  aria-invalid={erroHora && !parte.valida}
                  aria-describedby={erroHora ? `${id}-hora-erro` : undefined}
                  onChange={(e) => parte.mudar(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") { e.preventDefault(); aplicar(); }
                  }} />
              </label>
            ))}
          </div>
          {erroHora && <p id={`${id}-hora-erro`} className="erro" role="alert">
            Informe hora de 00 a 23 e minuto de 00 a 59.
          </p>}
          <div className="acoes">
            <button type="button" onClick={fechar}>Cancelar</button>
            <button type="button" onClick={aplicar}>Aplicar</button>
          </div>
        </div>
      )}
    </div>
  );
}
