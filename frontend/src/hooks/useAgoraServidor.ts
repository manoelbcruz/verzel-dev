import { useSyncExternalStore } from "react";
import { relogio } from "../lib/relogio";

export function useAgoraServidor() {
  useSyncExternalStore(relogio.assinarTique, relogio.tique);
  return relogio.agora();
}
