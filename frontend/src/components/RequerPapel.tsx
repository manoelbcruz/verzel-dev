import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router";
import { useSessao } from "../api/consultas";
import type { Papel } from "../api/tipos";
import Carregando from "./Carregando";
import MensagemErro from "./MensagemErro";

export default function RequerPapel({ papel, children }: { papel?: Papel; children: ReactNode }) {
  const sessao = useSessao();
  const local = useLocation();
  if (sessao.isPending) return <Carregando />;
  if (sessao.error) return <MensagemErro erro={sessao.error} />;
  if (!sessao.data) {
    return (
      <Navigate
        replace
        to={`/entrar?volta=${encodeURIComponent(local.pathname + local.search)}`}
      />
    );
  }
  if (papel && sessao.data.papel !== papel) {
    return (
      <p>Sua conta não tem permissão para esta página. <Link to="/">Voltar à vitrine</Link></p>
    );
  }
  return children;
}
