import { getRiskColor, getRiskLabel } from "../utils/risk.js";

// Demo data mirrors the real API shapes byte-for-byte so the UI never has to
// special-case a "fake" mode. It is always rendered behind the Demo data badge.

const RUN = "demo-run-01";
const VM = "vm-demo-01";

const DEMO_STEPS = [
  { step: "01", name: "1/7 signal-received", at_utc: "off", elapsed_ms: 1.2 },
  { step: "02", name: "2/7 checkpoint-saved", at_utc: "off", elapsed_ms: 142.8 },
  { step: "03", name: "3/7 migration-logged", at_utc: "off", elapsed_ms: 214.4 },
  { step: "04", name: "4/7 replacement-provisioned", at_utc: "off", elapsed_ms: 1289.6 },
  { step: "05", name: "5/7 checkpoint-downloaded", at_utc: "off", elapsed_ms: 1741.1 },
  { step: "06", name: "6/7 app-resumed", at_utc: "off", elapsed_ms: 2168.3 },
  { step: "07", name: "7/7 old-instance-terminated", at_utc: "off", elapsed_ms: 2248.9 },
];

function stamp(base, hoursAgo) {
  return new Date(base - hoursAgo * 3600 * 1000).toISOString();
}

export function demoStatus() {
  return {
    run_id: RUN,
    vm_id: VM,
    region: "ap-south-1",
    cpu_percent: 41.3,
    ram_percent: 38.7,
    risk_percent: 22.0,
    migration_count: 6,
    last_downtime_seconds: 2.1,
  };
}

function demoTimelineEntries(elapsedOffsets) {
  const base = Date.now();
  let acc = 0;
  return DEMO_STEPS.map((s, i) => {
    acc += elapsedOffsets[i];
    return {
      ...s,
      at_utc: new Date(base - 3600_000 + acc).toISOString(),
      elapsed_ms: acc,
    };
  });
}

export function demoTimeline() {
  const offsets = [1.2, 141.6, 71.6, 1075.2, 451.5, 427.2, 80.6];
  return demoTimelineEntries(offsets);
}

export function demoResult(now = Date.now()) {
  const tl = demoTimeline();
  return {
    run_id: RUN,
    from_vm_id: VM,
    to_vm_id: `${VM}-target`,
    migration_id: `demo-mig-${Math.floor(now / 1000) % 1_000_000}`,
    status: "completed",
    checkpoint_key: `checkpoints/${RUN}/cp-${new Date(now).toISOString().replace(/[:.]/g, "-")}.json`,
    downtime_seconds: 2.78,
    timeline: tl,
  };
}

export function demoHistory(base = Date.now()) {
  const rows = [
    {
      run_id: RUN,
      timestamp: stamp(base, 0.02),
      from_vm_id: `${VM}-target`,
      to_vm_id: VM,
      triggered_by: "imds",
      risk_percent: 88.4,
      downtime_seconds: 2.78,
      status: "completed",
      checkpoint_key: `checkpoints/${RUN}/cp-2026-09-16-10-31-22.json`,
      resumed_index: 36,
      provision_market: "spot",
      timeline: JSON.stringify(demoTimeline()),
      completed_at: stamp(base, 0.02),
    },
    {
      run_id: RUN,
      timestamp: stamp(base, 5.1),
      from_vm_id: VM,
      to_vm_id: `${VM}-target`,
      triggered_by: "prediction",
      risk_percent: 74.2,
      downtime_seconds: 3.02,
      status: "completed",
      checkpoint_key: `checkpoints/${RUN}/cp-2026-09-16-10-11-40.json`,
      resumed_index: 31,
      provision_market: "ondemand",
      timeline: JSON.stringify(demoTimeline()),
      completed_at: stamp(base, 5.1),
    },
    {
      run_id: RUN,
      timestamp: stamp(base, 47),
      from_vm_id: `${VM}-target`,
      to_vm_id: VM,
      triggered_by: "imds",
      risk_percent: 91.6,
      downtime_seconds: 2.64,
      status: "completed",
      checkpoint_key: `checkpoints/${RUN}/cp-2026-09-16-09-18-05.json`,
      resumed_index: 25,
      provision_market: "spot",
      timeline: JSON.stringify(demoTimeline()),
      completed_at: stamp(base, 47),
    },
  ];
  return { run_id: RUN, migrations: rows };
}

export function demoSeries(now = Date.now()) {
  const out = [];
  for (let i = 239; i >= 0; i -= 1) {
    const t = now - i * 3000;
    const phase = Math.sin(i / 9) * 9;
    out.push({
      t,
      cpu: 41 + phase + (i % 5),
      ram: 38 + Math.cos(i / 6) * 4,
      risk: 22 + ((i * 7) % 6) - 3,
    });
  }
  return out;
}

export { getRiskColor, getRiskLabel };