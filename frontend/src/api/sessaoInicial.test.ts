import { ANA, BRUNO } from "../test/dados";

it.each([ANA, null])("boot da sessão não é troca de identidade: %s", async (usuario) => {
  vi.resetModules();
  const {
    criarCliente, registrarConexao, obterGeracao, trocarIdentidade,
  } = await import("./sessao");
  const cliente = criarCliente();
  const reiniciar = vi.fn();
  const remover = registrarConexao({ reiniciar });
  const cancelar = vi.spyOn(cliente, "cancelQueries");
  const redefinir = vi.spyOn(cliente, "resetQueries");
  try {
    await cliente.fetchQuery({ queryKey: ["sessao"], queryFn: async () => usuario });
    expect(cliente.getQueryData(["sessao"])).toEqual(usuario);
    expect(obterGeracao()).toBe(0);
    expect(cancelar).not.toHaveBeenCalled();
    expect(redefinir).not.toHaveBeenCalled();
    expect(reiniciar).not.toHaveBeenCalled();
    trocarIdentidade(cliente, { reiniciar }, BRUNO);
    expect(obterGeracao()).toBe(1);
    expect(reiniciar).toHaveBeenCalledTimes(1);
  } finally {
    remover();
    cliente.clear();
  }
});
