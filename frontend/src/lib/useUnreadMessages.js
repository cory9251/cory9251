import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";

/**
 * Polls /api/messages/unread-count every `intervalMs`.
 * Returns { count, refresh }.
 */
export function useUnreadMessages(intervalMs = 10000) {
  const [count, setCount] = useState(0);
  const timerRef = useRef(null);

  const refresh = async () => {
    try {
      const { data } = await api.get("/messages/unread-count");
      setCount(data?.count ?? 0);
    } catch {
      // silent — auth errors etc.
    }
  };

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(refresh, intervalMs);
    const onChange = () => refresh();
    window.addEventListener("hcob:messages-changed", onChange);
    return () => {
      clearInterval(timerRef.current);
      window.removeEventListener("hcob:messages-changed", onChange);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs]);

  return { count, refresh };
}
