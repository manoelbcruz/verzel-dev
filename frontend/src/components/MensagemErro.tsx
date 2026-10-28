import { ErroApi } from "../api/http";
import { mensagemDeErro } from "../lib/erros";
import type { ContextoErro } from "../lib/erros";

export default function MensagemErro({ erro, contexto, porId = false }: {
  erro: unknown;
  contexto?: ContextoErro;
  porId?: boolean;
}) {
  if (!erro) return null;
  const texto =
    porId && erro instanceof ErroApi && erro.status === 422 && erro.codigo === "entrada_invalida"
      ? "Página ou recurso não encontrado."
      : mensagemDeErro(erro, contexto);
  return <p role="alert" className="erro">{texto}</p>;
}
