import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { relogio } from "../lib/relogio";

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal("matchMedia", vi.fn((media: string) => ({
    matches: false,
    media,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })));
  vi.stubGlobal("WebSocket", class {
    constructor() {
      throw new Error("WebSocket real proibido nos testes");
    }
  });
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  relogio.redefinir();
  document.documentElement.classList.remove("dark");
});
