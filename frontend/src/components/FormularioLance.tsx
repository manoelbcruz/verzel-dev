import { useEffect, useRef, useState } from "react";
import type { Fase, LoteDetalhe, Usuario } from "../api/tipos";
import { useDarLance } from "../api/mutacoes";
import { formatarCentavos, parseReais } from "../lib/dinheiro";
import Dinheiro from "./Dinheiro";
import CampoReais from "./CampoReais";
import MensagemErro from "./MensagemErro";

export default function FormularioLance({ lote, usuario, fase }: {
  lote: LoteDetalhe;
  usuario: Usuario | null;
  fase: Fase;
}) {
  const [editado, setEditado] = useState<string | null>(null);
  const [erroCampo, setErroCampo] = useState<string>();
  const minimoValido = Number.isSafeInteger(lote.proximo_lance_minimo_centavos);
  const minimo = minimoValido
    ? formatarCentavos(lote.proximo_lance_minimo_centavos)
    : "valor inválido";
  const texto = editado ?? minimo.replace(/^R\$\s*/, "");
  const lance = useDarLance(lote.id);
  const minimoAnterior = useRef(lote.proximo_lance_minimo_centavos);
  const aceitoEm = useRef<number | null>(null);
  const [avisoMinimo, setAvisoMinimo] = useState("");
  useEffect(() => {
    if (lance.ultimoAceito) {
      aceitoEm.current = Date.now();
      setEditado(null);
      setAvisoMinimo("");
    }
  }, [lance.ultimoAceito]);
  useEffect(() => {
    const acabouDeAceitar = lance.estado === "aceito"
      && aceitoEm.current !== null && Date.now() - aceitoEm.current < 5000;
    if (editado !== null || lote.minha_participacao?.ganhando || acabouDeAceitar) {
      setAvisoMinimo("");
    } else if (lote.proximo_lance_minimo_centavos > minimoAnterior.current) {
      setAvisoMinimo(`O mínimo subiu para ${minimo}`);
    }
    minimoAnterior.current = lote.proximo_lance_minimo_centavos;
  }, [
    lote.proximo_lance_minimo_centavos, lote.minha_participacao?.ganhando,
    minimo, editado, lance.estado,
  ]);
  useEffect(() => {
    if (!avisoMinimo) return;
    const timer = setTimeout(() => setAvisoMinimo(""), 5000);
    return () => clearTimeout(timer);
  }, [avisoMinimo]);
  const bloqueado =
    !minimoValido ||
    lance.estado === "enviando" ||
    usuario?.papel !== "licitante" ||
    fase !== "ao_vivo";

  return (
    <form noValidate onSubmit={(e) => {
      e.preventDefault();
      if (bloqueado) return;
      setAvisoMinimo("");
      const valor = parseReais(texto);
      if (!valor.ok) {
        setErroCampo(valor.erro);
        return;
      }
      setErroCampo(undefined);
      void lance.enviar(valor.centavos);
    }}>
      <CampoReais
        rotulo="Seu lance (R$)"
        valor={texto}
        mudar={(valor) => {
          setAvisoMinimo("");
          setEditado(valor);
        }}
        erro={erroCampo}
        disabled={bloqueado}
      />
      <p role="status">{avisoMinimo}</p>
      <div className="acoes">
        <button type="button" disabled={bloqueado} onClick={() => setEditado(null)}>
          Usar mínimo ({minimo})
        </button>
        <button className="primario" disabled={bloqueado}>Dar lance</button>
      </div>
      <MensagemErro erro={lance.erro} contexto={{ operacao: "lance", inicioEm: lote.inicio_em }} />
      {lance.estado === "incerto" && (
        <button type="button" disabled={bloqueado} onClick={() => {
          setAvisoMinimo("");
          void lance.repetir();
        }}>
          Tentar de novo
        </button>
      )}
      {lance.estado === "aceito" && lance.ultimoAceito && (
        <p role="status">
          Lance de <Dinheiro centavos={lance.ultimoAceito.valor_centavos} /> registrado.
        </p>
      )}
    </form>
  );
}
