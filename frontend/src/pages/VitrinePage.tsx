import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { useVitrine } from "../api/consultas";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import { useRefetchNosLimites } from "../hooks/useRefetchNosLimites";
import { faseEfetiva } from "../lib/fase";
import CartaoLote from "../components/CartaoLote";
import Carregando from "../components/Carregando";
import MensagemErro from "../components/MensagemErro";

export default function VitrinePage() {
  const [params, setParams] = useSearchParams();
  const [texto, setTexto] = useState(params.get("q") ?? "");
  const q = params.get("q") ?? "";
  const filtro = params.get("fase") ?? "todos";
  useEffect(() => setTexto(q), [q]);
  useEffect(() => {
    if (texto === q) return;
    const timer = setTimeout(
      () =>
        setParams(
          (anteriores) => {
            const novos = new URLSearchParams(anteriores);
            if (texto.trim()) novos.set("q", texto.trim());
            else novos.delete("q");
            return novos;
          },
          { replace: true },
        ),
      300,
    );
    return () => clearTimeout(timer);
  }, [texto, q, setParams]);
  const consulta = useVitrine(q);
  const agora = useAgoraServidor();
  const lotes = consulta.data
    ? [...consulta.data.ao_vivo, ...consulta.data.agendados, ...consulta.data.encerrados].filter(
        (l) => l.fase !== "cancelado",
      )
    : [];
  useRefetchNosLimites(consulta.refetch, lotes.flatMap((l) => [l.inicio_em, l.fim_em]));

  return (
    <>
      <section className="abertura">
        <p className="sobretitulo">COLECIONE HISTÓRIAS</p>
        <h1>Uma nova forma de<br />encontrar sua próxima obra.</h1>
        <p>Explore o acervo aberto do Met e participe de leilões em tempo real.</p>
      </section>
      <div className="filtros">
        <label>
          Buscar por título
          <input
            type="search"
            value={texto}
            maxLength={200}
            onChange={(e) => setTexto(e.target.value)}
            placeholder="Que obra você procura?"
          />
        </label>
        <div className="acoes">
          {[
            ["todos", "Todos"],
            ["ao_vivo", "Ao vivo"],
            ["agendado", "Agendados"],
            ["encerrado", "Encerrados"],
          ].map(([valor, rotulo]) => (
            <button
              key={valor}
              aria-pressed={filtro === valor}
              onClick={() =>
                setParams((anteriores) => {
                  const novos = new URLSearchParams(anteriores);
                  novos.set("fase", valor);
                  return novos;
                })
              }
            >
              {rotulo}
            </button>
          ))}
        </div>
      </div>
      <MensagemErro erro={consulta.error} />
      {consulta.isPending && <Carregando />}
      {consulta.data &&
        [
          ["ao_vivo", "Ao vivo"],
          ["agendado", "Agendados"],
          ["encerrado", "Encerrados"],
        ]
          .filter(([fase]) => filtro === "todos" || filtro === fase)
          .map(([fase, rotulo]) => {
            const grupo = lotes.filter((l) => faseEfetiva(l, agora) === fase);
            return (
              <section key={fase} className="secao">
                <h2>{rotulo} <span className="quantidade">{grupo.length}</span></h2>
                {!grupo.length && <p>Nenhum lote nesta seção.</p>}
                <div className="grade">
                  {grupo.map((lote) => <CartaoLote key={lote.id} lote={lote} />)}
                </div>
              </section>
            );
          })}
    </>
  );
}
