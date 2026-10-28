import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";

import App from "./App";
import { criarCliente } from "./api/sessao";
import { TempoRealProvider } from "./tempoReal/TempoRealProvider";
import "./index.css";

const queryClient = criarCliente();
const root = document.getElementById("root");

if (!root) {
  throw new Error("Elemento raiz não encontrado");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <TempoRealProvider><App /></TempoRealProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
