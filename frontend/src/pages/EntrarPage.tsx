import { useRef, useState } from "react";
import { Link, Navigate, useSearchParams } from "react-router";
import { useDemo, useSessao } from "../api/consultas";
import { useAutenticar } from "../api/mutacoes";
import { validarEmail, validarSenha } from "../lib/validacao";
import { caminhoSeguro, destinoAutenticado } from "../lib/navegacao";
import { useAvisoSessao } from "../api/sessao";
import MensagemErro from "../components/MensagemErro";
import Carregando from "../components/Carregando";

export default function EntrarPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erros, setErros] = useState<Record<string, string | undefined>>({});
  const emailRef = useRef<HTMLInputElement>(null);
  const senhaRef = useRef<HTMLInputElement>(null);
  const sessao = useSessao();
  const demo = useDemo();
  const login = useAutenticar();
  const [params] = useSearchParams();
  const volta = caminhoSeguro(params.get("volta"));
  const aviso = useAvisoSessao();
  if (sessao.isPending) return <Carregando />;
  if (sessao.data) return <Navigate replace to={destinoAutenticado(sessao.data, volta)} />;

  return (
    <section className="formulario-central">
      <h1>Entre na sua conta</h1>
      {aviso && <p role="status">{aviso}</p>}
      <p>Continue a disputa ou prepare seu próximo leilão.</p>
      <form noValidate onSubmit={(e) => {
        e.preventDefault();
        const problemas = { email: validarEmail(email), senha: validarSenha(senha) };
        setErros(problemas);
        if (problemas.email || problemas.senha) {
          (problemas.email ? emailRef : senhaRef).current?.focus();
          return;
        }
        void login.enviar({ email, senha });
      }}>
        <label>
          E-mail
          <input
            type="email"
            autoComplete="email"
            ref={emailRef}
            aria-invalid={!!erros.email}
            aria-describedby={erros.email ? "entrar-email-erro" : undefined}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        {erros.email && (
          <span id="entrar-email-erro" className="erro">{erros.email}</span>
        )}
        <label>
          Senha
          <input
            type="password"
            autoComplete="current-password"
            ref={senhaRef}
            aria-invalid={!!erros.senha}
            aria-describedby={erros.senha ? "entrar-senha-erro" : undefined}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </label>
        {erros.senha && (
          <span id="entrar-senha-erro" className="erro">{erros.senha}</span>
        )}
        <button className="primario" disabled={login.estado === "enviando"}>Entrar</button>
        <MensagemErro erro={login.erro} />
      </form>
      <p>
        Primeira visita?{" "}
        <Link to={volta ? `/cadastro?volta=${encodeURIComponent(volta)}` : "/cadastro"}>
          Criar conta
        </Link>
      </p>
      {demo.data && (
        <section className="acesso-rapido" aria-labelledby="acesso-rapido-titulo">
          <h2 id="acesso-rapido-titulo">Acesso rápido para avaliação</h2>
          <p>Contas de demonstração com saldo simulado, recriadas pelo seed.</p>
          <div className="acesso-rapido-botoes">
            {demo.data.contas.map((conta) => (
              <button
                key={conta.email}
                type="button"
                disabled={login.estado === "enviando"}
                onClick={() => {
                  if (demo.data?.senha) {
                    void login.enviar({ email: conta.email, senha: demo.data.senha });
                  } else {
                    setEmail(conta.email);
                  }
                }}
              >
                Entrar como {conta.rotulo}
              </button>
            ))}
          </div>
        </section>
      )}
    </section>
  );
}
