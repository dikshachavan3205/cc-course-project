// Single-metric line chart for the Telemetry Stream deep-dive. Same
// tokenized styling as LiveChart — hairline gridlines, custom tooltip, zero
// shadows — but one dataset, so CPU and RAM get dedicated analytical panels.
// No risk accents here; the resource series stay in neutral tokens.
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
} from 'chart.js';
import { Line } from 'react-chartjs-2';

import { fmtClock } from '../lib/time';
import { readCssVarRgb, rgbString } from '../lib/tokens';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip);

export default function MetricChart({ title, series = [], dataKey, rgb, heightClass = 'h-40' }) {
  const reducedMotion =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const color = rgbString(rgb);
  const gridColor = rgbString(readCssVarRgb('border-mid'), 0.3);
  const tickColor = rgbString(readCssVarRgb('text-muted'));
  const panelBg = rgbString(readCssVarRgb('bg-surface'));
  const borderMid = rgbString(readCssVarRgb('border-mid'));

  const data = {
    labels: series.map((p) => fmtClock(p.t)),
    datasets: [
      {
        label: title,
        data: series.map((p) => p[dataKey]),
        borderColor: color,
        backgroundColor: rgbString(rgb, 0.08),
        fill: true,
        tension: 0.3,
        pointRadius: 0,
        borderWidth: 2,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    animation: reducedMotion ? false : { duration: 300, easing: 'easeOutCubic' },
    interaction: { mode: 'index', intersect: false },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: panelBg,
        borderColor: borderMid,
        borderWidth: 1,
        titleColor: tickColor,
        bodyColor: rgbString(readCssVarRgb('text-primary')),
        displayColors: false,
        titleFont: { family: 'Space Grotesk, sans-serif', weight: '600' },
        bodyFont: { family: 'IBM Plex Mono, ui-monospace, monospace' },
        callbacks: {
          label: (item) => ` ${item.dataset.label}: ${item.parsed.y.toFixed(1)}%`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: tickColor, maxTicksLimit: 6, font: { family: 'IBM Plex Mono, ui-monospace, monospace', size: 11 } },
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: gridColor },
        ticks: { color: tickColor, callback: (v) => `${v}%`, font: { family: 'IBM Plex Mono, ui-monospace, monospace', size: 11 } },
      },
    },
  };

  return (
    <section className="panel p-5" aria-label={`${title} chart`}>
      <p className="panel-label">{title}</p>
      <div className={`mt-4 ${heightClass}`}>
        {series.length > 0 ? (
          <Line data={data} options={options} />
        ) : (
          <div className="grid h-full place-items-center text-sm text-muted">
            waiting for /status…
          </div>
        )}
      </div>
    </section>
  );
}