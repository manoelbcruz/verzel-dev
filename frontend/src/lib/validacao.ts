export function exigir(valor: string, mensagem = "Preencha este campo.") {
  return valor.trim() ? undefined : mensagem;
}

export function validarEmail(valor: string) {
  return exigir(valor) ?? (
    /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(valor) ? undefined : "Informe um e-mail válido."
  );
}

export function validarSenha(valor: string) {
  return exigir(valor) ?? (
    valor.length < 8 ? "Mínimo de 8 caracteres."
      : valor.length > 128 ? "Máximo de 128 caracteres." : undefined
  );
}
