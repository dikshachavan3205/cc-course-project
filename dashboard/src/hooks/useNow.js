// Live clock tick — drives "relative time" labels so "4s ago" keeps
// rolling on screen without refetching anything.
import { useEffect, useState } from 'react';

export default function useNow(intervalMs = 1000) {
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return now;
}