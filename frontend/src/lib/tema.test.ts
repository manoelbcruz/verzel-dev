import { aplicarTema, lerTema, salvarTema } from "./tema";
it("segue sistema e persiste escolha", () => {
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  expect(lerTema()).toBe("sistema");
  aplicarTema("sistema");
  expect(document.documentElement).toHaveClass("dark");
  salvarTema("escuro");
  expect(lerTema()).toBe("escuro");
  salvarTema("claro");
  expect(document.documentElement).not.toHaveClass("dark");
  localStorage.clear();
  vi.unstubAllGlobals();
});
