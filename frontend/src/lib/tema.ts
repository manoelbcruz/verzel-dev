export type Tema = "sistema" | "claro" | "escuro";
const CHAVE = "casa-de-leiloes:tema";

export function lerTema(): Tema {
  try {
    const valor = localStorage.getItem(CHAVE);
    return valor === "claro" || valor === "escuro" ? valor : "sistema";
  } catch {
    return "sistema";
  } // Preferência é opcional em navegadores sem armazenamento.
}

export function aplicarTema(tema: Tema) {
  document.documentElement.classList.toggle(
    "dark",
    tema === "escuro" || (tema === "sistema" && matchMedia("(prefers-color-scheme: dark)").matches),
  );
}

export function salvarTema(tema: Tema) {
  try {
    localStorage.setItem(CHAVE, tema);
  } catch {
    /* O tema segue funcionando nesta aba. */
  }
  aplicarTema(tema);
}
