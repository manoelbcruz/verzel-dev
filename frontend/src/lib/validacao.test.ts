import { exigir, validarEmail, validarSenha } from "./validacao";

it("exige conteúdo e permite mensagem específica", () => {
  expect(exigir("  ")).toBe("Preencha este campo.");
  expect(exigir("", "Informe o nome.")).toBe("Informe o nome.");
  expect(exigir("Nome")).toBeUndefined();
});

it.each(["sem-arroba", "a@b", "a@@b.com", "a b@c.com", " a@b.com"])(
  "recusa e-mail inválido %s", (valor) => {
    expect(validarEmail(valor)).toBe("Informe um e-mail válido.");
  },
);

it("aceita e-mail com domínio e valida limites de senha", () => {
  expect(validarEmail("pessoa@exemplo.com.br")).toBeUndefined();
  expect(validarEmail("")).toBe("Preencha este campo.");
  expect(validarSenha("")).toBe("Preencha este campo.");
  const senha = crypto.getRandomValues(new Uint32Array(8)).join("");
  expect(validarSenha(senha.slice(0, 7))).toBe("Mínimo de 8 caracteres.");
  expect(validarSenha(senha.slice(0, 8))).toBeUndefined();
  expect(validarSenha(senha.repeat(3).slice(0, 128))).toBeUndefined();
  expect(validarSenha(senha.repeat(3).slice(0, 129))).toBe("Máximo de 128 caracteres.");
});
