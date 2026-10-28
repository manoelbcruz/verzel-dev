import { useRef, useState } from "react";
import { Navigate, useSearchParams } from "react-router";
import { useSessao } from "../api/consultas";
import { useAutenticar } from "../api/mutacoes";
import type { Papel } from "../api/tipos";
import { caminhoSeguro, destinoAutenticado } from "../lib/navegacao";
import { exigir, validarEmail, validarSenha } from "../lib/validacao";
import { errosPorCampo } from "../lib/erros";
import MensagemErro from "../components/MensagemErro";

export default function CadastroPage() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [papel, setPapel] = useState<Papel>("licitante");
  const [errosLocais, setErrosLocais] = useState<Record<string, string | undefined>>({});
  const campos = useRef<Record<string, HTMLInputElement | null>>({});
  const cadastro = useAutenticar(true);
  const sessao = useSessao();
  const [params] = useSearchParams();
  const erros = { ...errosPorCampo(cadastro.erro), ...errosLocais };
  const volta = caminhoSeguro(params.get("volta"));
  if (sessao.data) return <Navigate replace to={destinoAutenticado(sessao.data, volta)} />;

  return (
    <section className="formulario-central">
      <h1>Criar conta</h1>
      <form noValidate onSubmit={async (e) => {
        e.preventDefault();
        const problemas = {
          nome: exigir(nome), email: validarEmail(email), senha: validarSenha(senha),
        };
        setErrosLocais(problemas);
        const primeiro = Object.entries(problemas).find(([, mensagem]) => mensagem);
        if (primeiro) {
          campos.current[primeiro[0]]?.focus();
          return;
        }
        setErrosLocais({});
        await cadastro.enviar({ nome, email, senha, papel });
      }}>
        {[
          ["nome", "Nome", nome, setNome],
          ["email", "E-mail", email, setEmail],
          ["senha", "Senha", senha, setSenha],
        ].map(([chave, rotulo, valor, mudar]) => (
          <div key={chave as string} className="campo">
            <label htmlFor={`cadastro-${chave}`}>
              {rotulo as string}
              <input
                id={`cadastro-${chave}`}
                ref={(elemento) => { campos.current[chave as string] = elemento; }}
                type={chave === "senha"
                  ? "password"
                  : chave === "email" ? "email" : "text"}
                maxLength={chave === "senha"
                  ? 128
                  : chave === "nome" ? 80 : 254}
                value={valor as string}
                onChange={(e) => {
                  (mudar as (v: string) => void)(e.target.value);
                  setErrosLocais((atuais) => ({ ...atuais, [chave as string]: undefined }));
                }}
                aria-invalid={!!erros[chave as string]}
                aria-describedby={
                  [
                    chave === "senha" ? "senha-ajuda" : "",
                    erros[chave as string] ? `erro-${chave}` : "",
                  ].filter(Boolean).join(" ") || undefined
                }
              />
            </label>
            {chave === "senha" && <span id="senha-ajuda">Mínimo de 8 caracteres</span>}
            {erros[chave as string] && (
              <span className="erro" id={`erro-${chave}`}>{erros[chave as string]}</span>
            )}
          </div>
        ))}
        <fieldset>
          <legend>Como você quer participar?</legend>
          <label>
            <input
              type="radio"
              name="papel"
              checked={papel === "licitante"}
              onChange={() => setPapel("licitante")}
            /> Quero dar lances
          </label>
          <label>
            <input
              type="radio"
              name="papel"
              checked={papel === "leiloeiro"}
              onChange={() => setPapel("leiloeiro")}
            /> Quero leiloar itens
          </label>
        </fieldset>
        <button className="primario" disabled={cadastro.estado === "enviando"}>Criar conta</button>
        <MensagemErro erro={cadastro.erro} contexto={{ operacao: "cadastro" }} />
      </form>
    </section>
  );
}
