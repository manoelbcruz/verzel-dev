import { faseEfetiva, proximoLimite } from "./fase";
import type { LoteResumo } from "../api/tipos";
it("muda nos limites exatos e preserva cancelamento", () => {
  const lote = {
    fase: "agendado", resultado: null,
    inicio_em: new Date(1000).toISOString(), fim_em: new Date(2000).toISOString(),
  } as LoteResumo;
  expect(faseEfetiva(lote, 999)).toBe("agendado");
  expect(faseEfetiva(lote, 1000)).toBe("ao_vivo");
  expect(faseEfetiva(lote, 2000)).toBe("encerrado");
  expect(faseEfetiva({ ...lote, fase: "cancelado" }, 1000)).toBe("cancelado");
  expect(proximoLimite(lote, 999)).toBe(lote.inicio_em);
  expect(proximoLimite(lote, 1000)).toBe(lote.fim_em);
  expect(proximoLimite(lote, 2000)).toBeNull();
});
