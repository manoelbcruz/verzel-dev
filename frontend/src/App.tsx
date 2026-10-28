import { Route, Routes } from "react-router";

import { useGeracao } from "./api/sessao";
import Layout from "./components/Layout";
import RequerPapel from "./components/RequerPapel";
import VitrinePage from "./pages/VitrinePage";
import SalaLotePage from "./pages/SalaLotePage";
import EntrarPage from "./pages/EntrarPage";
import CadastroPage from "./pages/CadastroPage";
import CarteiraPage from "./pages/CarteiraPage";
import MeusArrematesPage from "./pages/MeusArrematesPage";
import PainelLeiloeiroPage from "./pages/PainelLeiloeiroPage";
import NovoLotePage from "./pages/NovoLotePage";
import AuditoriaPage from "./pages/AuditoriaPage";
import ComprovantePage from "./pages/ComprovantePage";
import NaoEncontradoPage from "./pages/NaoEncontradoPage";

export default function App() {
  const geracao = useGeracao();
  return (
    <Layout>
      <Routes key={geracao}>
        <Route path="/" element={<VitrinePage />} />
        <Route path="/lotes/:loteId" element={<SalaLotePage />} />
        <Route path="/entrar" element={<EntrarPage />} />
        <Route path="/cadastro" element={<CadastroPage />} />
        <Route
          path="/carteira"
          element={<RequerPapel><CarteiraPage /></RequerPapel>}
        />
        <Route
          path="/arremates"
          element={<RequerPapel papel="licitante"><MeusArrematesPage /></RequerPapel>}
        />
        <Route
          path="/painel"
          element={<RequerPapel papel="leiloeiro"><PainelLeiloeiroPage /></RequerPapel>}
        />
        <Route
          path="/painel/novo"
          element={<RequerPapel papel="leiloeiro"><NovoLotePage /></RequerPapel>}
        />
        <Route path="/auditoria/:loteId" element={<AuditoriaPage />} />
        <Route path="/comprovantes/:codigo" element={<ComprovantePage />} />
        <Route path="*" element={<NaoEncontradoPage />} />
      </Routes>
    </Layout>
  );
}
