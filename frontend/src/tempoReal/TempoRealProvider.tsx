import { createContext, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { registrarConexao } from "../api/sessao";
import { ConexaoTempoReal, urlTempoReal } from "./conexao";
import type { EstadoConexao } from "./conexao";
import { criarDespachante } from "./despachar";

export const TempoRealContext = createContext<{ estado: EstadoConexao; conectado: boolean }>({
  estado: "desconectado",
  conectado: false,
});
export const useTempoReal = () => useContext(TempoRealContext);

export function TempoRealProvider({ children }: { children: ReactNode }) {
  const cliente = useQueryClient();
  const [estado, mudarEstado] = useState<EstadoConexao>("conectando");
  useEffect(() => {
    const despachante = criarDespachante(cliente);
    const conexao = new ConexaoTempoReal({
      url: urlTempoReal(location),
      aoMudarEstado: mudarEstado,
      aoReceber: despachante.despachar,
      aoFechar: (codigo) => {
        if (codigo === 4001) void cliente.invalidateQueries({ queryKey: ["sessao"] });
      },
    });
    const remover = registrarConexao(conexao);
    conexao.iniciar();
    return () => {
      remover();
      conexao.parar();
      despachante.parar();
    };
  }, [cliente]);
  return (
    <TempoRealContext.Provider value={{ estado, conectado: estado === "conectado" }}>
      {children}
    </TempoRealContext.Provider>
  );
}
