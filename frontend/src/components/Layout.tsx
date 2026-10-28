import { useEffect, type ReactNode } from "react";
import { matchPath, useLocation } from "react-router";
import { useGeracao } from "../api/sessao";
import Cabecalho from "./Cabecalho";
import IndicadorConexao from "./IndicadorConexao";
import LimiteErro from "./LimiteErro";
const TITULOS: [string, string][] = [
  ["/", "Vitrine"],
  ["/lotes/:loteId", "Sala do lote"],
  ["/entrar", "Entrar"],
  ["/cadastro", "Criar conta"],
  ["/carteira", "Minha carteira"],
  ["/arremates", "Meus arremates"],
  ["/painel", "Painel do leiloeiro"],
  ["/painel/novo", "Novo lote"],
  ["/auditoria/:loteId", "Auditoria"],
  ["/comprovantes/:codigo", "Comprovante de arremate"],
];
export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const geracao = useGeracao();
  useEffect(() => {
    const titulo = TITULOS.find(([caminho]) => matchPath(caminho, pathname))?.[1]
      ?? "Página não encontrada";
    document.title = `${titulo} · Casa de Leilões`;
  }, [pathname]);
  return (
    <>
      <a className="pular" href="#conteudo">Pular para o conteúdo</a>
      <Cabecalho />
      <main id="conteudo" tabIndex={-1}>
        <LimiteErro key={`${pathname}|${geracao}`}>{children}</LimiteErro>
      </main>
      <footer>
        <span>
          Casa de Leilões · Acervo aberto do Metropolitan Museum · Carteira com saldo simulado
        </span>
        <IndicadorConexao />
      </footer>
    </>
  );
}
