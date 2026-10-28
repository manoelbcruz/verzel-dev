(function () {
  var tema = "sistema";
  try {
    tema = localStorage.getItem("casa-de-leiloes:tema") || "sistema";
  } catch (_) { /* Sem armazenamento, segue o sistema. */ }
  try {
    document.documentElement.classList.toggle("dark", tema === "escuro" || (tema !== "claro" && matchMedia("(prefers-color-scheme: dark)").matches));
  } catch (_) { /* Navegador sem matchMedia mantém o tema claro. */ }
})();
