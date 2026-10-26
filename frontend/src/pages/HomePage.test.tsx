import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import HomePage from "./HomePage";

let queryClient: QueryClient;

afterEach(() => {
  cleanup();
  queryClient.clear();
  vi.unstubAllGlobals();
});

function renderHomePage() {
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <HomePage />
    </QueryClientProvider>,
  );
}

it("mostra API online quando o health responde com sucesso", async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify({ status: "ok" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);

  renderHomePage();

  expect(screen.getByText("Verificando API…")).toBeInTheDocument();
  expect(await screen.findByText("API online")).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith("/api/health");
});

it("mostra API indisponível quando o health responde 500", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 500 })));

  renderHomePage();

  expect(await screen.findByText("API indisponível")).toBeInTheDocument();
});
