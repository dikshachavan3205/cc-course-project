// Animates a numeric value toward a target with requestAnimationFrame.
// First run lasts --duration-arc (the risk meter's one orchestrated moment),
// later updates are short and smooth (--duration-value). No entrance
// re-animation on poll — pure value interpolation.
//
// prefers-reduced-motion: the meter skips straight to the end state — the
// initial value IS the target and every update lands immediately.
import { useEffect, useRef, useState } from 'react';

const FIRST = 1200;   // matches --duration-arc
const LATER = 300;    // matches --duration-value
const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

function prefersReducedMotion() {
  return (
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );
}

export default function useAnimatedValue(target, firstMs = FIRST, laterMs = LATER) {
  // Start at the target; the first effect pass then decides whether to animate
  // down/up to it or park immediately (reduced motion).
  const [value, setValue] = useState(() => Number(target) || 0);
  const reducedRef = useRef(prefersReducedMotion());
  const firstRef = useRef(true);
  const fromRef = useRef(value);
  const rafRef = useRef(null);

  useEffect(() => {
    if (reducedRef.current) {
      fromRef.current = Number(target) || 0;
      setValue(fromRef.current);
      firstRef.current = false;
      return;
    }

    cancelAnimationFrame(rafRef.current);
    const from = fromRef.current;
    const duration = firstRef.current ? firstMs : laterMs;
    firstRef.current = false;

    let start = null;
    const step = (ts) => {
      if (start === null) start = ts;
      const t = Math.min(1, (ts - start) / Math.max(1, duration));
      const v = from + (target - from) * easeOutCubic(t);
      setValue(v);
      fromRef.current = v;
      if (t < 1) rafRef.current = requestAnimationFrame(step);
    };
    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, firstMs, laterMs]);

  return Math.max(0, Math.min(100, Number(value) || 0));
}