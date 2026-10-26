import type { Observation } from "./api";

const W = 760;
const H = 240;
const PAD = { l: 34, r: 12, t: 12, b: 26 };

export function NdviChart({ obs }: { obs: Observation[] }) {
  if (obs.length === 0) return null;
  const iw = W - PAD.l - PAD.r;
  const ih = H - PAD.t - PAD.b;

  const t0 = new Date(obs[0].scene_date).getTime();
  const t1 = new Date(obs[obs.length - 1].scene_date).getTime();
  const span = Math.max(t1 - t0, 1);
  const x = (d: string) => PAD.l + ((new Date(d).getTime() - t0) / span) * iw;
  const y = (v: number) => PAD.t + (1 - Math.max(0, Math.min(1, v))) * ih;

  const meanLine = obs.map((o) => `${x(o.scene_date)},${y(o.ndvi_mean)}`).join(" ");
  const bandTop = obs.map((o) => `${x(o.scene_date)},${y(o.ndvi_p90)}`).join(" ");
  const bandBot = obs.map((o) => `${x(o.scene_date)},${y(o.ndvi_p10)}`).reverse().join(" ");
  const band = `${bandTop} ${bandBot}`;

  // month ticks
  const ticks: { x: number; label: string }[] = [];
  let last = "";
  for (const o of obs) {
    const d = new Date(o.scene_date);
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (key !== last) {
      ticks.push({ x: x(o.scene_date), label: d.toLocaleString("en", { month: "short" }) });
      last = key;
    }
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="ndvi-chart" role="img" aria-label="NDVI time series">
      {[0, 0.25, 0.5, 0.75, 1].map((g) => (
        <g key={g}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(g)} y2={y(g)} className="grid" />
          <text x={PAD.l - 6} y={y(g) + 3} className="ytick" textAnchor="end">{g}</text>
        </g>
      ))}
      {ticks.map((t, i) => (
        <text key={i} x={t.x} y={H - 8} className="xtick" textAnchor="middle">{t.label}</text>
      ))}
      <polygon points={band} className="ndvi-band" />
      <polyline points={meanLine} className="ndvi-line" />
      {obs.map((o) => (
        <circle key={o.scene_date} cx={x(o.scene_date)} cy={y(o.ndvi_mean)} r={2.4}
          className="ndvi-dot">
          <title>{o.scene_date}: NDVI {o.ndvi_mean.toFixed(2)}</title>
        </circle>
      ))}
    </svg>
  );
}
