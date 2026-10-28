import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router";
import { useItens } from "../api/consultas";
import { useCriarLote } from "../api/mutacoes";
import { requisitar } from "../api/http";
import type { ItemExterno, Vitrine } from "../api/tipos";
import { useAgoraServidor } from "../hooks/useAgoraServidor";
import { datetimeLocalParaIso, msParaDatetimeLocal } from "../lib/datas";
import { parseReais } from "../lib/dinheiro";
import { relogio } from "../lib/relogio";
import CampoDataHora from "../components/CampoDataHora";
import CampoReais from "../components/CampoReais";
import ListaAtributos from "../components/ListaAtributos";
import MensagemErro from "../components/MensagemErro";

export default function NovoLotePage() {
  const [texto, setTexto] = useState("");
  const [busca, setBusca] = useState("");
  const [pagina, setPagina] = useState(1);
  const datasInicializadas = useRef(false);
  const tituloFormulario = useRef<HTMLHeadingElement>(null);
  const [item, setItem] = useState<ItemExterno | null>(null);
  const [inicial, setInicial] = useState("100,00");
  const [incremento, setIncremento] = useState("10,00");
  const [inicio, setInicio] = useState("");
  const [fim, setFim] = useState("");
  const [imediato, setImediato] = useState(false);
  const [erros, setErros] = useState<Record<string, string>>({});
  const itens = useItens(busca, pagina);
  const criar = useCriarLote();
  const navegar = useNavigate();
  const agora = useAgoraServidor();
  const sincronizado = relogio.sincronizado();
  const sincronizar = useQuery({
    queryKey: ["vitrine", ""],
    queryFn: ({ signal }) => requisitar<Vitrine>("/lotes", { signal }),
    enabled: !sincronizado,
    staleTime: 0,
  });
  useEffect(() => {
    if (sincronizado && !datasInicializadas.current) {
      datasInicializadas.current = true;
      const proximo = (Math.floor(agora / 60000) + 1) * 60000;
      setInicio(msParaDatetimeLocal(proximo));
      setFim(msParaDatetimeLocal(proximo + 3600000));
    }
  }, [sincronizado, agora]);
  useEffect(() => {
    if (item) {
      tituloFormulario.current?.scrollIntoView({ block: "start", behavior: "smooth" });
      tituloFormulario.current?.focus({ preventScroll: true });
    }
  }, [item]);

  async function publicar() {
    if (!item || !sincronizado) return;
    const valor = parseReais(inicial);
    const passo = parseReais(incremento);
    const inicioIso = imediato
      ? new Date(relogio.agora()).toISOString()
      : datetimeLocalParaIso(inicio);
    const fimIso = datetimeLocalParaIso(fim);
    const problemas: Record<string, string> = {};
    if (!valor.ok) problemas.inicial = valor.erro;
    if (!passo.ok) problemas.incremento = passo.erro;
    const duracao = inicioIso && fimIso ? Date.parse(fimIso) - Date.parse(inicioIso) : 0;
    if (!imediato && !inicio) {
      problemas.datas = "Preencha o início.";
    } else if (!fim) {
      problemas.datas = "Preencha o fim.";
    } else if (
      !inicioIso ||
      !fimIso ||
      duracao < 60000 ||
      duracao > 30 * 86400000 ||
      Date.parse(inicioIso) < relogio.agora() - 300000
    ) {
      problemas.datas =
        "A duração deve ser de 1 minuto a 30 dias, " +
        "com início não anterior a cinco minutos atrás.";
    }
    setErros(problemas);
    if (Object.keys(problemas).length || !valor.ok || !passo.ok || !inicioIso || !fimIso) return;
    const lote = await criar.enviar({
      item_id_externo: item.id_externo,
      lance_inicial_centavos: valor.centavos,
      incremento_centavos: passo.centavos,
      inicio_em: inicioIso,
      fim_em: fimIso,
    });
    if (lote) navegar(`/lotes/${lote.id}`);
  }

  return (
    <>
      <Link to="/painel">← Painel</Link>
      <h1>Novo lote</h1>
      {!sincronizado && <p role="status">Sincronizando relógio</p>}
      <MensagemErro erro={sincronizar.error} />
      <form
        noValidate
        className="filtros"
        onSubmit={(e) => {
          e.preventDefault();
          setPagina(1);
          setBusca(texto.trim());
        }}
      >
        <label>
          Buscar no acervo do Met
          <input
            maxLength={200}
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
          />
        </label>
        <button disabled={!texto.trim()}>Buscar</button>
      </form>
      <MensagemErro erro={itens.error} />
      {busca && itens.isFetching && (
        <p role="status">Buscando no acervo do Met, pode levar alguns segundos</p>
      )}
      {itens.data && (
        <section className="secao">
          {itens.data.parcial && (
            <p role="status">Resultado parcial: alguns itens não puderam ser consultados.</p>
          )}
          {itens.data.origem === "cache" && <p role="status">Exibindo resultados do cache.</p>}
          {!itens.data.itens.length && (
            <p>
              {itens.data.tem_mais
                ? "Nenhum item elegível nesta página. Tente a próxima."
                : "Nenhum item elegível encontrado."}
            </p>
          )}
          <div className="grade">
            {itens.data.itens.map((obra) => (
              <article className="cartao" key={obra.id_externo}>
                <img
                  src={obra.imagem_url_externa}
                  alt={obra.titulo}
                  referrerPolicy="no-referrer"
                  loading="lazy"
                />
                <h2>{obra.titulo}</h2>
                <button
                  aria-pressed={item?.id_externo === obra.id_externo}
                  onClick={() => setItem(obra)}
                >
                  Selecionar {obra.titulo}
                </button>
              </article>
            ))}
          </div>
          <div className="acoes">
            <button
              disabled={pagina <= 1 || itens.isFetching}
              onClick={() => setPagina(pagina - 1)}
            >
              Página anterior
            </button>
            <span>Página {pagina}</span>
            <button
              disabled={!itens.data.tem_mais || itens.isFetching}
              onClick={() => setPagina(pagina + 1)}
            >
              Próxima página
            </button>
          </div>
        </section>
      )}
      {item && (
        <section className="sala">
          <div>
            <h2>{item.titulo}</h2>
            <img
              className="obra"
              src={item.imagem_url_externa}
              alt={item.titulo}
              referrerPolicy="no-referrer"
            />
            <ListaAtributos atributos={item.atributos} />
          </div>
          <form
            noValidate
            className="painel"
            onSubmit={(e) => {
              e.preventDefault();
              if (!e.currentTarget.checkValidity()) {
                e.currentTarget.querySelector<HTMLInputElement>("input:invalid")?.focus();
                return;
              }
              void publicar();
            }}
          >
            <h2 ref={tituloFormulario} tabIndex={-1}>Condições do leilão</h2>
            <CampoReais
              rotulo="Lance inicial (valor mínimo)"
              valor={inicial}
              mudar={setInicial}
              erro={erros.inicial}
            />
            <CampoReais
              rotulo="Incremento mínimo"
              valor={incremento}
              mudar={setIncremento}
              erro={erros.incremento}
            />
            <p>Datas no horário do seu navegador.</p>
            <label>
              <input
                type="checkbox"
                checked={imediato}
                onChange={(e) => setImediato(e.target.checked)}
              /> Começar agora
            </label>
            <CampoDataHora
              rotulo="Início"
              valor={inicio}
              desabilitado={imediato || !sincronizado}
              aoMudar={setInicio}
              invalido={!!erros.datas}
              descricaoId={erros.datas ? "datas-erro" : undefined}
            />
            <CampoDataHora
              rotulo="Fim"
              valor={fim}
              desabilitado={!sincronizado}
              aoMudar={setFim}
              invalido={!!erros.datas}
              descricaoId={erros.datas ? "datas-erro" : undefined}
            />
            {erros.datas && <p className="erro" id="datas-erro" role="alert">{erros.datas}</p>}
            <button className="primario" disabled={!sincronizado || criar.estado === "enviando"}>
              Publicar lote
            </button>
            <MensagemErro erro={criar.erro} />
            {criar.estado === "incerto" && (
              <p role="alert">
                Confira no <Link to="/painel">painel</Link> se o lote foi criado antes de
                tentar de novo.
              </p>
            )}
          </form>
        </section>
      )}
    </>
  );
}
