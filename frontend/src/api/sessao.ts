import { QueryCache, QueryClient } from "@tanstack/react-query";
import { useSyncExternalStore } from "react";
import { ErroApi } from "./http";
import type { Usuario } from "./tipos";

type Conexao = { reiniciar: () => void };
let identidade: string | null | undefined;
let avisoSessao: string | null = null;
let geracao = 0;
let conexaoAtual: Conexao | null = null;
let logoutEmCurso: object | null = null;
const assinantes = new Set<() => void>();
export const conexaoSessao: Conexao = { reiniciar: () => conexaoAtual?.reiniciar() };
export const obterGeracao = () => geracao;

export function registrarConexao(conexao: Conexao) {
  conexaoAtual = conexao;
  return () => {
    if (conexaoAtual === conexao) conexaoAtual = null;
  };
}

export function trocarIdentidade(
  cliente: QueryClient,
  conexao: Conexao,
  usuario: Usuario | null,
  iniciadaPeloUsuario = false,
) {
  if (usuario || iniciadaPeloUsuario) {
    avisoSessao = null;
    assinantes.forEach((cb) => cb());
  }
  const nova = usuario ? `${usuario.email}|${usuario.papel}` : null;
  if (nova === identidade) {
    cliente.setQueryData(["sessao"], usuario);
    return;
  }
  identidade = nova;
  if (nova !== null) logoutEmCurso = null;
  geracao++;
  void cliente.cancelQueries();
  cliente.setQueryData(["sessao"], usuario);
  for (const chave of ["carteira", "participacoes", "painel", "lote"]) {
    void cliente.resetQueries({ queryKey: [chave] });
  }
  conexao.reiniciar();
  assinantes.forEach((cb) => cb());
}

export function expirarSessao(cliente: QueryClient) {
  avisoSessao = logoutEmCurso ? null : "Sua sessão expirou. Entre de novo.";
  trocarIdentidade(cliente, conexaoSessao, null);
  assinantes.forEach((cb) => cb());
}

export function iniciarLogout() {
  const tentativa = {};
  logoutEmCurso = tentativa;
  avisoSessao = null;
  assinantes.forEach((cb) => cb());
  return () => {
    if (logoutEmCurso === tentativa) logoutEmCurso = null;
  };
}

export function useAvisoSessao() {
  return useSyncExternalStore(
    (cb) => {
      assinantes.add(cb);
      return () => { assinantes.delete(cb); };
    },
    () => avisoSessao,
  );
}

export function useGeracao() {
  return useSyncExternalStore(
    (cb) => {
      assinantes.add(cb);
      return () => { assinantes.delete(cb); };
    },
    obterGeracao,
  );
}

export function criarCliente() {
  const cliente: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onSuccess(dados, query) {
        if (query.queryKey[0] !== "sessao") return;
        const usuario = dados as Usuario | null;
        if (identidade === undefined) {
          identidade = usuario ? `${usuario.email}|${usuario.papel}` : null;
          return;
        }
        if (!usuario && identidade !== null) expirarSessao(cliente);
        else trocarIdentidade(cliente, conexaoSessao, usuario);
      },
      onError(erro) {
        if (erro instanceof ErroApi && erro.status === 401 && erro.codigo === "nao_autenticado") {
          expirarSessao(cliente);
        }
      },
    }),
    defaultOptions: {
      queries: {
        staleTime: 5000,
        refetchOnWindowFocus: true,
        retry: (vez, erro) =>
          erro instanceof ErroApi && (erro.status === 0 || erro.status >= 500) && vez < 2,
      },
      mutations: { retry: false },
    },
  });
  return cliente;
}
