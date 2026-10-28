import { useId } from "react";

export default function CampoReais({ rotulo, valor, mudar, erro, disabled }: {
  rotulo: string;
  valor: string;
  mudar: (valor: string) => void;
  erro?: string;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      <input
        id={id}
        inputMode="decimal"
        value={valor}
        disabled={disabled}
        onChange={(e) => mudar(e.target.value)}
        aria-invalid={!!erro}
        aria-describedby={erro ? `${id}-erro` : undefined}
      />
      {erro && <p id={`${id}-erro`} className="erro">{erro}</p>}
    </div>
  );
}
