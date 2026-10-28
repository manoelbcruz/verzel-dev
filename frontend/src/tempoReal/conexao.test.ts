import { ConexaoTempoReal, urlTempoReal } from "./conexao";
import { SocketFalso } from "../test/utilitarios";

function criar() {
  vi.useFakeTimers();
  const sockets: SocketFalso[] = [];
  const estado = vi.fn();
  const recebeu = vi.fn();
  const fechou = vi.fn();
  const conexao = new ConexaoTempoReal({
    url: "ws://localhost:3000/ws",
    criarSocket: (url) => {
      const socket = new SocketFalso(url);
      sockets.push(socket);
      return socket;
    },
    aoMudarEstado: estado,
    aoReceber: recebeu,
    aoFechar: fechou,
    aleatorio: () => 1,
  });
  conexao.iniciar();
  return { conexao, sockets, estado, recebeu, fechou };
}

it("URL da mesma origem e estado conectado só no ola", () => {
  expect(urlTempoReal({ protocol: "http:", host: "localhost:3000" }))
    .toBe("ws://localhost:3000/ws");
  expect(urlTempoReal({ protocol: "https:", host: "leilao.example" }))
    .toBe("wss://leilao.example/ws");
  const { conexao, sockets, estado, recebeu } = criar();
  sockets[0].abrir();
  expect(estado).not.toHaveBeenCalledWith("conectado");
  sockets[0].receber("inválido");
  sockets[0].receber({ v: 2, tipo: "ping" });
  expect(recebeu).not.toHaveBeenCalled();
  sockets[0].receber({ v: 1, tipo: "ola", autenticado: false });
  expect(estado).toHaveBeenLastCalledWith("conectado");
  conexao.parar();
});

it("espera 1, 2, 4 segundos até 30 e zera no ola", () => {
  const { conexao, sockets } = criar();
  for (const espera of [1000, 2000, 4000, 8000, 16000, 30000, 30000]) {
    const antes = sockets.length;
    sockets.at(-1)!.fecharPeloServidor(1006);
    vi.advanceTimersByTime(espera - 1);
    expect(sockets).toHaveLength(antes);
    vi.advanceTimersByTime(1);
    expect(sockets).toHaveLength(antes + 1);
  }
  sockets.at(-1)!.receber({ v: 1, tipo: "ola", autenticado: true });
  sockets.at(-1)!.fecharPeloServidor(1006);
  const antes = sockets.length;
  vi.advanceTimersByTime(1000);
  expect(sockets).toHaveLength(antes + 1);
  conexao.parar();
});

it("vigia silêncio, ping renova, 4001 e reiniciar reconectam, parar termina", () => {
  const { conexao, sockets, fechou } = criar();
  vi.advanceTimersByTime(59000);
  sockets[0].receber({ v: 1, tipo: "ping" });
  vi.advanceTimersByTime(59000);
  expect(sockets[0].readyState).not.toBe(3);
  vi.advanceTimersByTime(1000);
  expect(sockets[0].readyState).toBe(3);
  vi.advanceTimersByTime(1000);
  expect(sockets).toHaveLength(2);
  sockets[1].fecharPeloServidor(4001);
  vi.advanceTimersByTime(0);
  expect(sockets).toHaveLength(3);
  expect(fechou).toHaveBeenCalledWith(4001);
  conexao.reiniciar();
  expect(sockets).toHaveLength(4);
  conexao.parar();
  vi.advanceTimersByTime(120000);
  expect(sockets).toHaveLength(4);
});
