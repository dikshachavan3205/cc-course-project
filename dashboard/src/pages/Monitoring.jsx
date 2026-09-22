import { useMemo } from "react";
import { ChartPanel, LineChart } from "../components/Charts.jsx";
import { PageHead } from "../components/layout.jsx";
import { useChrono } from "../hooks/useChrono.js";
import { getRiskColor } from "../utils/risk.js";
import { todayHMS } from "../lib/time.js";

const MAX_POINTS = 300;

function downsample(series, max = MAX_POINTS) {
  if (!series || series.length <= max) {
    return {
      labels: (series || []).map((p) => todayHMS(p.t)),
      cpu: (series || []).map((p) => p.cpu),
      ram: (series || []).map((p) => p.ram),
      risk: (series || []).map((p) => p.risk),
    };
  }
  const step = Math.ceil(series.length / max);
  const picked = series.filter((_, i) => i % step === 0);
  return {
    labels: picked.map((p) => todayHMS(p.t)),
    cpu: picked.map((p) => p.cpu),
    ram: picked.map((p) => p.ram),
    risk: picked.map((p) => p.risk),
  };
}

export default function Monitoring() {
  const { series, status } = useChrono();
  const { labels, cpu, ram, risk } = useMemo(() => downsample(series), [series]);
  const riskColor = getRiskColor(status?.risk_percent ?? 0);

  const windowNote = series && series.length >= 2 ? "~30 min window at the configured poll" : "buffer not full yet";

  return (
    <>
      <PageHead
        title="Monitoring"
        sub={`${windowNote}. Charts accumulate while this dashboard is open.`}
      />

      <div className="grid grid-cols-1 gap-4">
        <ChartPanel title="CPU & memory" height={280} extra={<span className="text-xs text-muted">{`${labels.length} samples`}</span>}>
          <LineChart
            labels={labels}
            datasets={[
              { label: "CPU %", data: cpu, stroke: "rgba(201,218,232,0.95)" },
              { label: "RAM %", data: ram, stroke: "rgba(143,176,201,0.7)" },
            ]}
            yFormat={(v) => `${v.toFixed(1)}%`}
          />
        </ChartPanel>

        <ChartPanel title="Risk" height={280} extra={<span className="text-xs text-muted">{`${labels.length} samples`}</span>}>
          <LineChart
            labels={labels}
            datasets={[{ label: "Risk %", data: risk, stroke: riskColor }]}
            yFormat={(v) => `${v.toFixed(1)}%`}
          />
        </ChartPanel>
      </div>
    </>
  );
}