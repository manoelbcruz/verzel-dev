export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`/api${path}`);
  if (!response.ok) {
    throw new Error(`Erro na API: ${response.status}`);
  }
  return response.json() as Promise<T>;
}
