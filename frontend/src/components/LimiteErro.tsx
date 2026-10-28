import { Component, type ReactNode } from "react";

export default class LimiteErro extends Component<{ children: ReactNode }, { falhou: boolean }> {
  state = { falhou: false };

  static getDerivedStateFromError() {
    return { falhou: true };
  }

  render() {
    if (this.state.falhou) {
      return (
        <section role="alert">
          <h1>Não foi possível exibir esta página.</h1>
          <p>Tente novamente ou volte à vitrine.</p>
          <a href="/">Voltar à vitrine</a>
        </section>
      );
    }
    return this.props.children;
  }
}
