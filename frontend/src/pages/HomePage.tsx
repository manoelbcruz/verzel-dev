import { useQuery } from "@tanstack/react-query";

import { apiGet } from "../api/client";

export default function HomePage() {
  const { isPending, isError } = useQuery({
    queryKey: ["health"],
    queryFn: () => apiGet<{ status: string }>("/health"),
  });

  const status = isPending
    ? "Verificando API…"
    : isError
      ? "API indisponível"
      : "API online";

  return (
    <main className="min-h-screen bg-slate-50 px-6 py-16 text-slate-900">
      <div className="mx-auto max-w-3xl rounded-2xl border border-slate-200 bg-white p-8">
        <h1 className="text-3xl font-bold">Casa de Leilões</h1>
        <p role="status" className="mt-4 text-slate-600">
          {status}
        </p>
      </div>
    </main>
  );
}
