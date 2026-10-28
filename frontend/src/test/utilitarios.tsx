import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { criarCliente, conexaoSessao, trocarIdentidade } from "../api/sessao";
import type { Usuario } from "../api/tipos";
import { TempoRealContext } from "../tempoReal/TempoRealProvider";

export function criarClienteTeste() {
  const cliente = criarCliente();
  cliente.setDefaultOptions({
    queries: { retry: false, gcTime: Infinity, staleTime: Infinity },
    mutations: { retry: false },
  });
  return cliente;
}

export function renderizar(ui: ReactNode, {
  rota = "/",
  caminho = "*",
  usuario = null,
  conectado = true,
  cliente = criarClienteTeste(),
}: {
  rota?: string;
  caminho?: string;
  usuario?: Usuario | null;
  conectado?: boolean;
  cliente?: ReturnType<typeof criarClienteTeste>;
} = {}) {
  trocarIdentidade(cliente, conexaoSessao, usuario);
  const resultado = render(
    <QueryClientProvider client={cliente}>
      <MemoryRouter initialEntries={[rota]}>
        <TempoRealContext.Provider value={{
          estado: conectado ? "conectado" : "desconectado", conectado,
        }}>
          <Routes><Route path={caminho} element={ui} /></Routes>
        </TempoRealContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...resultado, cliente };
}

export type Requisicao = {
  metodo: string;
  caminho: string;
  headers: Headers;
  corpo: Record<string, unknown>;
};

export function respostaJson(dados: unknown, status = 200) {
  return new Response(status === 204 ? null : JSON.stringify(dados), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function simularApi(
  rotas: Record<string, unknown | ((pedido: Requisicao) => unknown | Promise<unknown>)>,
) {
  const pedidos: Requisicao[] = [];
  const fetch = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const pedido = {
      metodo: init?.method ?? "GET",
      caminho: String(url),
      headers: new Headers(init?.headers),
      corpo: init?.body ? JSON.parse(String(init.body)) : {},
    };
    pedidos.push(pedido);
    const rota = rotas[`${pedido.metodo} ${pedido.caminho}`];
    if (rota === undefined) return respostaJson({ erro: { codigo: "nao_encontrado" } }, 404);
    const resultado = typeof rota === "function" ? await rota(pedido) : rota;
    return resultado instanceof Response ? resultado : respostaJson(resultado);
  });
  vi.stubGlobal("fetch", fetch);
  return { pedidos, fetch };
}

export class SocketFalso {
  readyState = 0;
  onopen: WebSocket["onopen"] = null;
  onmessage: WebSocket["onmessage"] = null;
  onclose: WebSocket["onclose"] = null;
  onerror: WebSocket["onerror"] = null;
  constructor(public url: string) {}

  abrir() {
    this.readyState = 1;
    this.onopen?.call(this as unknown as WebSocket, new Event("open"));
  }

  receber(dados: unknown) {
    this.onmessage?.call(this as unknown as WebSocket, new MessageEvent("message", {
      data: typeof dados === "string" ? dados : JSON.stringify(dados),
    }));
  }

  fecharPeloServidor(code: number) {
    this.readyState = 3;
    this.onclose?.call(this as unknown as WebSocket, new CloseEvent("close", { code }));
  }

  close() {
    this.fecharPeloServidor(1000);
  }

  send() {
    throw new Error("O cliente não envia mensagens");
  }
}
