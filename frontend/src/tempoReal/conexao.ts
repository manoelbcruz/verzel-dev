import { interpretarMensagem } from "./mensagens";
import type { Mensagem } from "./mensagens";

export type EstadoConexao = "conectando" | "conectado" | "desconectado";
export type Socket = Pick<WebSocket, "onopen" | "onmessage" | "onclose" | "onerror" | "close">;
type Opcoes = {
  url: string;
  criarSocket?: (url: string) => Socket;
  aoMudarEstado: (estado: EstadoConexao) => void;
  aoReceber: (msg: Mensagem) => void;
  aoFechar?: (codigo: number) => void;
  aleatorio?: () => number;
};
export const urlTempoReal = (local: Pick<Location, "protocol" | "host">) =>
  `${local.protocol === "https:" ? "wss:" : "ws:"}//${local.host}/ws`;

export class ConexaoTempoReal {
  private socket: Socket | null = null;
  private timer?: ReturnType<typeof setTimeout>;
  private guarda?: ReturnType<typeof setTimeout>;
  private tentativas = 0;
  private parada = true;

  constructor(private opcoes: Opcoes) {}

  iniciar() {
    if (this.parada) {
      this.parada = false;
      this.abrir();
    }
  }

  private limparSocket() {
    clearTimeout(this.guarda);
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onopen = socket.onmessage = socket.onclose = socket.onerror = null;
      socket.close();
    }
  }

  private vigiar() {
    clearTimeout(this.guarda);
    this.guarda = setTimeout(() => {
      this.limparSocket();
      this.reconectar();
    }, 60000);
  }

  private reconectar(codigo = 1006) {
    if (this.parada) return;
    this.opcoes.aoMudarEstado("desconectado");
    this.opcoes.aoFechar?.(codigo);
    const espera = codigo === 4001
      ? 0
      : Math.min(30000, 1000 * 2 ** Math.min(this.tentativas++, 5)) *
        (0.5 + (this.opcoes.aleatorio ?? Math.random)() / 2);
    this.timer = setTimeout(() => this.abrir(), espera);
  }

  private abrir() {
    if (this.parada) return;
    this.opcoes.aoMudarEstado("conectando");
    let socket: Socket;
    try {
      socket = (this.opcoes.criarSocket ?? ((url) => new WebSocket(url)))(this.opcoes.url);
    } catch {
      this.reconectar();
      return;
    }
    this.socket = socket;
    this.vigiar();
    socket.onmessage = (evento) => {
      if (socket !== this.socket) return;
      this.vigiar();
      const msg = interpretarMensagem(String(evento.data));
      if (!msg) return;
      if (msg.tipo === "ola") {
        this.tentativas = 0;
        this.opcoes.aoMudarEstado("conectado");
      }
      this.opcoes.aoReceber(msg);
    };
    socket.onclose = (evento) => {
      if (socket !== this.socket) return;
      this.limparSocket();
      this.reconectar(evento.code);
    };
    socket.onerror = () => {
      if (socket !== this.socket) return;
      this.limparSocket();
      this.reconectar();
    };
  }

  reiniciar() {
    this.parada = false;
    clearTimeout(this.timer);
    this.limparSocket();
    this.abrir();
  }

  parar() {
    this.parada = true;
    clearTimeout(this.timer);
    this.limparSocket();
  }
}
