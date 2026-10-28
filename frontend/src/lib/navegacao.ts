import type { Usuario } from "../api/tipos";

export function caminhoSeguro(caminho: string | null | undefined) {
  return caminho?.startsWith("/") &&
    !caminho.startsWith("//") &&
    !caminho.includes("\\") &&
    !/[\u0000-\u0020]/.test(caminho)
    ? caminho
    : null;
}

export function destinoAutenticado(usuario: Usuario, volta: string | null) {
  return caminhoSeguro(volta) ?? (usuario.papel === "leiloeiro" ? "/painel" : "/");
}
