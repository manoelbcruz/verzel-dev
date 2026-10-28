import { formatarCentavos } from "../lib/dinheiro";

export default function Dinheiro({ centavos }: { centavos: number }) {
  return (
    <span className="dinheiro">
      {Number.isSafeInteger(centavos) ? formatarCentavos(centavos) : "valor inválido"}
    </span>
  );
}
