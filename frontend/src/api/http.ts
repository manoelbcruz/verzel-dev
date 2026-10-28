import { relogio } from "../lib/relogio";

export class ErroApi extends Error {
  constructor(
    public status: number,
    public codigo: string,
    public mensagem = "",
    public detalhes: Record<string, unknown> = {},
  ) {
    super(mensagem || codigo);
  }
}

type Opcoes = {
  metodo?: "GET" | "POST";
  corpo?: unknown;
  idempotencia?: string;
  signal?: AbortSignal;
};

export async function requisitar<T>(caminho: string, opcoes: Opcoes = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opcoes.corpo !== undefined) headers["Content-Type"] = "application/json";
  if (opcoes.idempotencia) headers["Idempotency-Key"] = opcoes.idempotencia;
  const antes = Date.now();
  let resposta: Response;
  try {
    resposta = await fetch(`/api${caminho}`, {
      method: opcoes.metodo ?? "GET",
      credentials: "same-origin",
      headers,
      body: opcoes.corpo === undefined ? undefined : JSON.stringify(opcoes.corpo),
      signal: opcoes.signal,
    });
  } catch (erro) {
    if (erro && typeof erro === "object" && "name" in erro && erro.name === "AbortError") {
      throw erro;
    }
    throw new ErroApi(0, "falha_rede");
  }
  const depois = Date.now();
  const data = resposta.headers.get("Date");
  if (data) relogio.registrar(data, antes, depois, false);
  if (resposta.status === 204) return undefined as T;
  let corpo;
  try {
    corpo = await resposta.json();
  } catch {
    throw new ErroApi(
      resposta.status,
      [502, 503, 504].includes(resposta.status) ? "servico_indisponivel" : "erro_interno",
    );
  }
  if (!resposta.ok) {
    throw new ErroApi(
      resposta.status,
      corpo?.erro?.codigo ?? "erro_interno",
      corpo?.erro?.mensagem,
      corpo?.erro?.detalhes,
    );
  }
  if (typeof corpo?.servidor_agora === "string") {
    relogio.registrar(corpo.servidor_agora, antes, depois);
  }
  return corpo as T;
}
