import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { getRiskColor, getRiskLabel } from "../utils/risk.js";
import { Panel, PanelLabel } from "./ui.jsx";
import { useChrono } from "../hooks/useChrono.js";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Filler, Tooltip, Legend);

ChartJS.defaults.font.family = "IBM Plex Mono, monospace";
ChartJS.defaults.font.size = 11;
ChartJS.defaults.color = "rgba(143,176,201,0.85)";

const GRID = "rgba(77,114,143,0.12)";

export function LineChart({ labels, datasets, height = 220, yFormat = (v) => v }) {
  const data = {
    labels,
    datasets: datasets.map((d) => ({
      label: d.label,
      data: d.data,
      borderColor: d.stroke,
      backgroundColor: d.fill || "rgba(0,0,0,0)",
      borderWidth: 1.5,
      borderDash: d.dash,
      pointRadius: 0,
      tension: 0.32,
      fill: Boolean(d.fill),
    })),
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        backgroundColor: "rgba(0,0,42,0.92)",
        borderColor: "rgba(77,114,143,0.5)",
        borderWidth: 1,
        titleColor: "rgba(201,218,232,1)",
        bodyColor: "rgba(143,176,201,1)",
        padding: 10,
        callbacks: {
          label: (ctx) => `${ctx.dataset.label}: ${yFormat(ctx.parsed.y)}`,
        },
      },
    },
    scales: {
      x: {
        ticks: { autoSkip: true, maxTicksLimit: 8, maxRotation: 0 },
        grid: { color: GRID },
        border: { color: "rgba(77,114,143,0.3)" },
      },
      y: {
        ticks: { maxTicksLimit: 5 },
        grid: { color: GRID },
        border: { display: false },
      },
    },
  };

  return (
    <div style={{ height }} className="w-full">
      <Line data={data} options={options} />
    </div>
  );
}

export function ChartPanel({ title, children, height, extra }) {
  return (
    <Panel className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <PanelLabel>{title}</PanelLabel>
        {extra || <LiveDot />}
      </div>
      {children || <LineChart height={height} labels={[]} datasets={[]} />}
    </Panel>
  );
}

function LiveDot() {
  const { connected } = useChrono();
  const color = connected ? "var(--risk-low)" : "var(--risk-medium)";
  return (
    <span className="flex items-center gap-1.5 text-xs text-muted">
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} aria-hidden="true" />
      live
    </span>
  );
}

export function RiskArc({ risk, size = 200 }) {
  const pct = Math.max(0, Math.min(100, Number.isFinite(risk) ? risk : 0));
  const frac = pct / 100;
  const color = getRiskColor(pct);
  const label = getRiskLabel(pct);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 100" className="w-full" style={{ maxWidth: size }} aria-hidden="true">
        <path
          d="M24 90 A76 76 0 0 1 176 90"
          fill="none"
          stroke="rgba(77,114,143,0.28)"
          strokeWidth="9"
          strokeLinecap="round"
          pathLength={1}
        />
        <path
          d="M24 90 A76 76 0 0 1 176 90"
          fill="none"
          stroke={color}
          strokeWidth="9"
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset={1 - frac}
          className="arc-fill-once"
          style={{
            transition: "stroke-dashoffset 0.7s cubic-bezier(0.4,0,0.2,1), stroke 0.4s ease",
            ["--arc-length"]: 1,
          }}
        />
      </svg>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="num text-xl leading-none" style={{ color }}>
          {pct.toFixed(1)}%
        </span>
        <span className="text-sm text-muted">{label}</span>
      </div>
    </div>
  );
}