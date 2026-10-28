const ROTULOS: Record<string, string> = {
  artista: "Artista",
  data: "Data",
  cultura: "Cultura",
  tecnica: "Técnica",
  dimensoes: "Dimensões",
  departamento: "Departamento",
  classificacao: "Classificação",
  url_objeto: "Página no Met",
  credito: "Crédito",
  licenca: "Licença",
};

function urlSegura(valor: string) {
  try {
    return new URL(valor).protocol === "https:";
  } catch {
    return false;
  }
}

export default function ListaAtributos({ atributos }: { atributos: Record<string, string> }) {
  return (
    <dl className="atributos">
      {Object.entries(ROTULOS)
        .filter(([chave]) => atributos[chave])
        .map(([chave, rotulo]) => (
          <div key={chave}>
            <dt>{rotulo}</dt>
            <dd>
              {chave === "url_objeto" && urlSegura(atributos[chave]) ? (
                <a href={atributos[chave]} target="_blank" rel="noopener noreferrer">
                  Ver no Met ↗
                </a>
              ) : atributos[chave]}
            </dd>
          </div>
        ))}
    </dl>
  );
}
