import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ErroApi, requisitar } from "./http";
import {
  conexaoSessao,
  expirarSessao,
  iniciarLogout,
  obterGeracao,
  trocarIdentidade,
  useGeracao,
} from "./sessao";
import type {
  CadastroEntrada,
  Carteira,
  LanceAceito,
  LoginEntrada,
  LoteDetalhe,
  LoteEntrada,
  LoteResumo,
  Usuario,
} from "./tipos";
import { proximaTentativa } from "../lib/idempotencia";
import type { Tentativa } from "../lib/idempotencia";

export type EstadoMutacao = "ocioso" | "enviando" | "aceito" | "recusado" | "incerto";
const incerto = (erro: unknown) =>
  erro instanceof ErroApi &&
  ["falha_rede", "servico_indisponivel", "servico_ocupado", "erro_interno"].includes(erro.codigo);

export function useComando<E, S>(
  executar: (entrada: E) => Promise<S>,
  sucesso: (saida: S) => void,
) {
  const cliente = useQueryClient();
  const geracaoAtual = useGeracao();
  const ocupado = useRef<number | null>(null);
  const [geracaoEstado, setGeracaoEstado] = useState(geracaoAtual);
  const [estado, setEstado] = useState<EstadoMutacao>("ocioso");
  const [erro, setErro] = useState<unknown>(null);

  async function enviar(entrada: E) {
    const geracao = obterGeracao();
    if (ocupado.current === geracao) return;
    ocupado.current = geracao;
    setGeracaoEstado(geracao);
    setEstado("enviando");
    setErro(null);
    try {
      const saida = await executar(entrada);
      if (geracao !== obterGeracao()) return;
      setEstado("aceito");
      sucesso(saida);
      return saida;
    } catch (falha) {
      if (geracao !== obterGeracao()) return;
      if (falha instanceof ErroApi && falha.status === 401 && falha.codigo === "nao_autenticado") {
        expirarSessao(cliente);
        return;
      }
      setErro(falha);
      setEstado(incerto(falha) ? "incerto" : "recusado");
    } finally {
      if (ocupado.current === geracao) ocupado.current = null;
    }
  }
  return {
    enviar,
    estado: geracaoEstado === geracaoAtual ? estado : ("ocioso" as EstadoMutacao),
    erro: geracaoEstado === geracaoAtual ? erro : null,
  };
}

export function useAutenticar(cadastro = false) {
  const cliente = useQueryClient();
  return useComando<LoginEntrada | CadastroEntrada, Usuario>(
    (entrada) =>
      requisitar(cadastro ? "/auth/cadastro" : "/auth/login", { metodo: "POST", corpo: entrada }),
    (usuario) => trocarIdentidade(cliente, conexaoSessao, usuario),
  );
}

export function useSair() {
  const cliente = useQueryClient();
  return useComando<void, void>(
    async () => {
      const terminar = iniciarLogout();
      try {
        await requisitar("/auth/logout", { metodo: "POST" });
      } finally {
        terminar();
      }
    },
    () => trocarIdentidade(cliente, conexaoSessao, null, true),
  );
}

function useValor<S extends Carteira | LanceAceito>(alvo: string, operacao: "lance" | "deposito") {
  const cliente = useQueryClient();
  const tentativa = useRef<Tentativa | null>(null);
  const ocupado = useRef(false);
  const [estado, setEstado] = useState<EstadoMutacao>("ocioso");
  const [erro, setErro] = useState<unknown>(null);
  const [ultimoAceito, setUltimo] = useState<S | null>(null);

  async function enviar(valor: number) {
    if (ocupado.current) return;
    const geracao = obterGeracao();
    const atual = proximaTentativa(tentativa.current, alvo, valor);
    tentativa.current = atual;
    ocupado.current = true;
    setEstado("enviando");
    setErro(null);
    setUltimo(null);
    try {
      const saida = await requisitar<S>(alvo, {
        metodo: "POST",
        corpo: { valor_centavos: valor },
        idempotencia: atual.chave,
      });
      if (geracao !== obterGeracao()) return;
      tentativa.current = null;
      setUltimo(saida);
      setEstado("aceito");
      // Replay de depósito contém o saldo antigo: o GET sempre traz o saldo atual.
      for (const chave of operacao === "lance"
        ? [["lote", alvo.split("/")[2]], ["carteira"], ["participacoes"]]
        : [["carteira"]]) {
        void cliente.invalidateQueries({ queryKey: chave });
      }
    } catch (falha) {
      if (geracao !== obterGeracao()) return;
      if (falha instanceof ErroApi && falha.status === 401 && falha.codigo === "nao_autenticado") {
        expirarSessao(cliente);
        return;
      }
      atual.incerta = incerto(falha);
      tentativa.current = atual.incerta ? atual : null;
      setErro(falha);
      setEstado(atual.incerta ? "incerto" : "recusado");
      if (operacao === "lance") {
        void cliente.invalidateQueries({ queryKey: ["lote", alvo.split("/")[2]] });
      }
    } finally {
      ocupado.current = false;
    }
  }
  return {
    enviar,
    repetir: () => (tentativa.current?.incerta ? enviar(tentativa.current.valor) : undefined),
    estado,
    erro,
    ultimoAceito,
  };
}

export const useDarLance = (id: string) =>
  useValor<LanceAceito>(`/lotes/${id.toLowerCase()}/lances`, "lance");
export const useDepositar = () => useValor<Carteira>("/carteira/depositos", "deposito");

export function useCancelar() {
  const cliente = useQueryClient();
  return useComando<string, LoteResumo>(
    (id) => requisitar(`/leiloeiro/lotes/${id}/cancelar`, { metodo: "POST" }),
    (lote) => {
      for (const chave of [["painel"], ["vitrine"], ["lote", lote.id]]) {
        void cliente.invalidateQueries({ queryKey: chave });
      }
    },
  );
}

export function useCriarLote() {
  const cliente = useQueryClient();
  return useComando<LoteEntrada, LoteDetalhe>(
    (entrada) => requisitar("/leiloeiro/lotes", { metodo: "POST", corpo: entrada }),
    () => {
      void cliente.invalidateQueries({ queryKey: ["painel"] });
      void cliente.invalidateQueries({ queryKey: ["vitrine"] });
    },
  );
}
