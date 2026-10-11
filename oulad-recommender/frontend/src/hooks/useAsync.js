import { useCallback, useEffect, useState } from "react";

export function useAsync(fn, deps = []) {
  const [state, set] = useState({ data: null, error: null, loading: true });
  const run = useCallback(async () => {
    try { set((s) => ({ ...s, loading: true })); set({ data: await fn(), error: null, loading: false }); }
    catch (e) { set({ data: null, error: e.message, loading: false }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { ...state, reload: run };
}
