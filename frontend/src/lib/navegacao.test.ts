import { caminhoSeguro } from "./navegacao";

it.each([
  "//evil.com", "/\\evil.com", "https://evil", "javascript:alert(1)", "", "/\nevil.com",
])("recusa redirecionamento %s", (caminho) => expect(caminhoSeguro(caminho)).toBeNull());

it("aceita caminho local", () => expect(caminhoSeguro("/lotes/x")).toBe("/lotes/x"));
