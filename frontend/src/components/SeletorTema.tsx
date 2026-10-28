import { useTema } from "../hooks/useTema";
import Dica from "./Dica";

const temas = [
  { valor: "claro", rotulo: "Tema claro", desenho:
    "M12 3v1m0 16v1M3 12h1m16 0h1M5.6 5.6l.7.7m11.4 11.4.7.7M5.6 18.4l.7-.7M17.7 6.3l.7-.7" },
  { valor: "escuro", rotulo: "Tema escuro", desenho:
    "M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10Z" },
  { valor: "sistema", rotulo: "Tema do sistema", desenho:
    "M3 4h18v13H3ZM8 21h8m-4-4v4" },
] as const;

export default function SeletorTema() {
  const { tema, escolher } = useTema();
  return (
    <div className="tema" role="group" aria-label="Tema">
      {temas.map(({ valor, rotulo, desenho }) => (
        <Dica key={valor} texto={valor === "sistema" ? "Seguir o sistema" : rotulo}
          focavel={false}>
          <button
            type="button"
            aria-label={rotulo}
            aria-pressed={tema === valor}
            onClick={() => escolher(valor)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true"
              stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <path d={desenho} />
              {valor === "claro" && <circle cx="12" cy="12" r="4" />}
            </svg>
          </button>
        </Dica>
      ))}
    </div>
  );
}
