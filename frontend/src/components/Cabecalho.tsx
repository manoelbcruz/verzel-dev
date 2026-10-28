import { Link, NavLink } from "react-router";
import { useSessao } from "../api/consultas";
import { useSair } from "../api/mutacoes";
import SeletorTema from "./SeletorTema";
import MensagemErro from "./MensagemErro";

export default function Cabecalho() {
  const sessao = useSessao();
  const sair = useSair();
  return (
    <header className="cabecalho">
      <div className="cabecalho-conteudo">
        <Link className="marca" to="/">
          Casa de Leilões<span>Arte aberta. Disputas ao vivo.</span>
        </Link>
        <nav aria-label="Principal">
          <NavLink to="/">Vitrine</NavLink>
          {sessao.data && <NavLink to="/carteira">Carteira</NavLink>}
          {sessao.data?.papel === "licitante" && <NavLink to="/arremates">Meus arremates</NavLink>}
          {sessao.data?.papel === "leiloeiro" && <NavLink to="/painel">Painel</NavLink>}
        </nav>
        <div className="conta">
          <SeletorTema />
          {sessao.isPending ? (
            <span className="conta-carregando">Carregando conta…</span>
          ) : sessao.data ? (
            <div className="conta-usuario">
              <span className="conta-nome">{sessao.data.nome}</span>
              <button onClick={() => void sair.enviar()} disabled={sair.estado === "enviando"}>
                Sair
              </button>
            </div>
          ) : (
            <div className="conta-acoes">
              <Link className="botao" to="/entrar">
                Entrar
              </Link>
              <Link className="botao primario" to="/cadastro">
                Criar conta
              </Link>
            </div>
          )}
        </div>
        <MensagemErro erro={sessao.error || sair.erro} />
      </div>
    </header>
  );
}
