import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { chaves } from "./chaves";
import { ErroApi, requisitar } from "./http";
import type {
  Carteira,
  ContasDemo,
  Comprovante,
  LoteDetalhe,
  PaginaItens,
  PainelLeiloeiro,
  Participacao,
  RelatorioAuditoria,
  Usuario,
  Vitrine,
} from "./tipos";
import { useIntervaloPolling } from "../hooks/useIntervaloPolling";
import { faseEfetiva } from "../lib/fase";
import { relogio } from "../lib/relogio";

export function useSessao() {
  return useQuery({
    queryKey: chaves.sessao,
    staleTime: 60000,
    queryFn: async ({ signal }) => {
      try {
        return await requisitar<Usuario>("/auth/me", { signal });
      } catch (erro) {
        if (erro instanceof ErroApi && erro.status === 401 && erro.codigo === "nao_autenticado") {
          return null;
        }
        throw erro;
      }
    },
  });
}

export function useVitrine(q: string) {
  return useQuery({
    queryKey: chaves.vitrine(q),
    placeholderData: keepPreviousData,
    queryFn: ({ signal }) =>
      requisitar<Vitrine>(`/lotes${q ? `?q=${encodeURIComponent(q)}` : ""}`, { signal }),
    refetchInterval: useIntervaloPolling("lista"),
  });
}

export function useLote(id: string) {
  const intervalo = useIntervaloPolling("sala");
  return useQuery({
    queryKey: chaves.lote(id),
    queryFn: ({ signal }) =>
      requisitar<LoteDetalhe>(`/lotes/${encodeURIComponent(id.toLowerCase())}`, { signal }),
    refetchInterval: (q) =>
      q.state.data &&
      faseEfetiva(q.state.data, relogio.agora()) === "encerrado" &&
      !q.state.data.resultado
        ? 3000
        : intervalo,
  });
}

export function useCarteira() {
  const sessao = useSessao();
  return useQuery({
    queryKey: chaves.carteira,
    queryFn: ({ signal }) => requisitar<Carteira>("/carteira", { signal }),
    enabled: !!sessao.data,
    refetchInterval: useIntervaloPolling("lista"),
  });
}

export function useParticipacoes() {
  const sessao = useSessao();
  return useQuery({
    queryKey: chaves.participacoes,
    queryFn: ({ signal }) => requisitar<Participacao[]>("/me/participacoes", { signal }),
    enabled: sessao.data?.papel === "licitante",
    refetchInterval: useIntervaloPolling("lista"),
  });
}

export function usePainel() {
  const sessao = useSessao();
  return useQuery({
    queryKey: chaves.painel,
    queryFn: ({ signal }) => requisitar<PainelLeiloeiro>("/leiloeiro/lotes", { signal }),
    enabled: sessao.data?.papel === "leiloeiro",
    refetchInterval: useIntervaloPolling("lista"),
  });
}

export const useAuditoria = (id: string) =>
  useQuery({
    queryKey: chaves.auditoria(id),
    queryFn: ({ signal }) =>
      requisitar<RelatorioAuditoria>(`/lotes/${encodeURIComponent(id.toLowerCase())}/auditoria`, {
        signal,
      }),
  });

export const useComprovante = (codigo: string) =>
  useQuery({
    queryKey: chaves.comprovante(codigo),
    queryFn: ({ signal }) =>
      requisitar<Comprovante>(`/comprovantes/${encodeURIComponent(codigo)}`, { signal }),
    staleTime: Infinity,
  });

export const useItens = (q: string, pagina: number) =>
  useQuery({
    queryKey: chaves.itens(q, pagina),
    placeholderData: keepPreviousData,
    retry: (vez, erro) =>
      erro instanceof ErroApi &&
      erro.codigo !== "api_externa_indisponivel" &&
      (erro.status === 0 || erro.status >= 500) &&
      vez < 2,
    queryFn: ({ signal }) =>
      requisitar<PaginaItens>(`/leiloeiro/itens?q=${encodeURIComponent(q)}&pagina=${pagina}`, {
        signal,
      }),
    enabled: !!q,
  });

export const useDemo = () =>
  useQuery({
    queryKey: ["demo"],
    queryFn: async ({ signal }) => {
      try {
        return await requisitar<ContasDemo>("/demo", { signal });
      } catch (erro) {
        if (erro instanceof ErroApi && erro.status === 404) return null;
        throw erro;
      }
    },
    staleTime: Infinity,
  });
