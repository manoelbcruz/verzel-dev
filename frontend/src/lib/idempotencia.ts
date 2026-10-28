export type Tentativa = { alvo: string; valor: number; chave: string; incerta: boolean };
export function novaChave(prefixo: string) {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return `${prefixo}-${Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("")}`;
}
export function proximaTentativa(
  anterior: Tentativa | null,
  alvo: string,
  valor: number,
): Tentativa {
  return anterior?.incerta && anterior.alvo === alvo && anterior.valor === valor
    ? anterior
    : { alvo, valor, chave: novaChave("pedido"), incerta: false };
}
