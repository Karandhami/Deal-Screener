import { useState, useEffect, useMemo } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, Cell,
} from "recharts";

// In dev this defaults to localhost; in production Vercel injects the real
// backend URL via VITE_API_URL (set in the Vercel dashboard).
const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

/* ------------------------------------------------------------------ *
 *  Deal Screening Engine — investor-grade dashboard
 *  Aesthetic: institutional luxury. Deep ink ground, Fraunces display
 *  over Archivo body, muted gold + deep green accents. Dense, calm,
 *  serious-money feel — the opposite of generic SaaS.
 * ------------------------------------------------------------------ */

const C = {
  ink: "#0B1A1F",
  panel: "#0F2429",
  panel2: "#132D33",
  line: "#1E3D44",
  gold: "#C8A24B",
  green: "#3FA788",
  greenDim: "#2A6F5C",
  red: "#C2603F",
  text: "#E8EDEB",
  textDim: "#8FA39E",
  textFaint: "#5C726D",
};

const recColor = (rec) =>
  (rec || "").startsWith("ADVANCE") ? C.green : (rec || "").startsWith("REVIEW") ? C.gold : C.red;

function fmtMoney(v) {
  if (v == null) return "—";
  const n = Number(v);
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}
function fmtPct(v) {
  return v == null ? "—" : `${(Number(v) * 100).toFixed(1)}%`;
}

export default function App() {
  const [thesis, setThesis] = useState(null);
  const [deals, setDeals] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState("mock"); // mock | tickers | upload
  const [tickers, setTickers] = useState("MSFT, CRM, NOW");
  const [file, setFile] = useState(null);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    fetch(`${API}/api/thesis/default`)
      .then((r) => r.json())
      .then(setThesis)
      .catch(() => setError("Cannot reach the API. Is the backend running on :8000?"));
  }, []);

  async function run() {
    setLoading(true);
    setError("");
    setSelected(0);
    try {
      let res;
      if (mode === "mock") {
        res = await fetch(`${API}/api/screen/mock`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(thesis),
        });
      } else if (mode === "tickers") {
        res = await fetch(`${API}/api/screen/tickers`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ thesis, tickers }),
        });
      } else {
        if (!file) throw new Error("Choose a CSV or Excel file first.");
        const fd = new FormData();
        fd.append("file", file);
        fd.append("thesis_json", JSON.stringify(thesis));
        res = await fetch(`${API}/api/screen/upload`, { method: "POST", body: fd });
      }
      if (!res.ok) throw new Error(`Server returned ${res.status}`);
      const data = await res.json();
      setDeals(data.deals);
      setSummary(data.summary);
      if (!data.deals.length) setError("No companies returned for that input.");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function patchThesis(key, value) {
    setThesis((t) => ({ ...t, [key]: value === "" ? null : Number(value) }));
  }

  const active = deals[selected];

  const chartData = useMemo(
    () =>
      deals.map((d) => ({
        name: d.company.name.length > 16 ? d.company.name.slice(0, 15) + "…" : d.company.name,
        score: Number(d.fit.overall_score),
        rec: d.fit.recommendation,
      })),
    [deals]
  );

  const radarData = useMemo(() => {
    if (!active || active.fit.hard_failed) return [];
    return active.fit.criteria.map((c) => ({
      criterion: c.name.replace(/_/g, " "),
      score: Number(c.score) * 100,
    }));
  }, [active]);

  return (
    <div style={S.root}>
      <style>{GLOBAL}</style>

      {/* ---- Masthead ---- */}
      <header style={S.header}>
        <div>
          <div style={S.eyebrow}>PRIVATE EQUITY · DEAL ORIGINATION</div>
          <h1 style={S.title}>Deal Screening Engine</h1>
        </div>
        <div style={S.headerMeta}>
          <span style={S.metaLabel}>MANDATE</span>
          <span style={S.metaValue}>{thesis?.name ?? "—"}</span>
        </div>
      </header>

      <div style={S.grid}>
        {/* ---- Left rail: mandate controls ---- */}
        <aside style={S.rail}>
          <SectionLabel>Source</SectionLabel>
          <div style={S.segmented}>
            {["mock", "tickers", "upload"].map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{ ...S.segBtn, ...(mode === m ? S.segBtnActive : {}) }}
              >
                {m === "mock" ? "Sample" : m === "tickers" ? "SEC Live" : "Upload"}
              </button>
            ))}
          </div>

          {mode === "tickers" && (
            <div style={{ marginTop: 14 }}>
              <label style={S.fieldLabel}>Tickers (comma-separated)</label>
              <input style={S.input} value={tickers} onChange={(e) => setTickers(e.target.value)} />
              <p style={S.hint}>Live from SEC EDGAR — no key needed.</p>
            </div>
          )}
          {mode === "upload" && (
            <div style={{ marginTop: 14 }}>
              <label style={S.fieldLabel}>Deal list (CSV / XLSX)</label>
              <input
                type="file"
                accept=".csv,.xlsx,.xls"
                onChange={(e) => setFile(e.target.files[0])}
                style={S.fileInput}
              />
              <p style={S.hint}>Columns: name, sector, revenue, ebitda, debt…</p>
            </div>
          )}

          <div style={S.divider} />
          <SectionLabel>Mandate Thresholds</SectionLabel>
          {thesis && (
            <div style={S.fields}>
              <Field label="Min revenue" v={thesis.min_revenue} onChange={(v) => patchThesis("min_revenue", v)} />
              <Field label="Max revenue" v={thesis.max_revenue} onChange={(v) => patchThesis("max_revenue", v)} />
              <Field label="Min rev. growth" v={thesis.min_revenue_growth} step="0.01" onChange={(v) => patchThesis("min_revenue_growth", v)} />
              <Field label="Min EBITDA margin" v={thesis.min_ebitda_margin} step="0.01" onChange={(v) => patchThesis("min_ebitda_margin", v)} />
              <Field label="Max net leverage" v={thesis.max_net_leverage} step="0.1" onChange={(v) => patchThesis("max_net_leverage", v)} />
              <Field label="Max EV / EBITDA" v={thesis.max_ev_ebitda} step="0.5" onChange={(v) => patchThesis("max_ev_ebitda", v)} />
            </div>
          )}

          <button style={S.runBtn} onClick={run} disabled={loading || !thesis}>
            {loading ? "Screening…" : "Run Screen"}
          </button>
          {error && <p style={S.error}>{error}</p>}
        </aside>

        {/* ---- Main canvas ---- */}
        <main style={S.main}>
          {summary && (
            <div style={S.kpiRow}>
              <Kpi label="Screened" value={summary.total} tone={C.text} />
              <Kpi label="Advance" value={summary.advance} tone={C.green} />
              <Kpi label="Review" value={summary.review} tone={C.gold} />
              <Kpi label="Pass" value={summary.pass} tone={C.red} />
            </div>
          )}

          {!deals.length && !loading && (
            <div style={S.empty}>
              <div style={S.emptyMark}>◆</div>
              <p style={S.emptyText}>
                Configure the mandate and run a screen. Results rank by thesis fit,
                with a generated screening memo for each target.
              </p>
            </div>
          )}

          {deals.length > 0 && (
            <>
              <Panel title="Thesis Fit — Ranked">
                <ResponsiveContainer width="100%" height={Math.max(180, deals.length * 42)}>
                  <BarChart data={chartData} layout="vertical" margin={{ left: 8, right: 24 }}>
                    <CartesianGrid horizontal={false} stroke={C.line} />
                    <XAxis type="number" domain={[0, 100]} stroke={C.textFaint} fontSize={11} />
                    <YAxis type="category" dataKey="name" width={120} stroke={C.textDim} fontSize={11} />
                    <Tooltip
                      cursor={{ fill: "rgba(255,255,255,0.03)" }}
                      contentStyle={S.tooltip}
                      formatter={(v) => [`${v}/100`, "Fit"]}
                    />
                    <Bar dataKey="score" radius={[0, 3, 3, 0]} onClick={(_, i) => setSelected(i)}>
                      {chartData.map((d, i) => (
                        <Cell key={i} fill={recColor(d.rec)} fillOpacity={i === selected ? 1 : 0.62} cursor="pointer" />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </Panel>

              <div style={S.detailGrid}>
                {/* deal list */}
                <Panel title="Pipeline" pad={false}>
                  <div style={S.list}>
                    {deals.map((d, i) => (
                      <button
                        key={i}
                        onClick={() => setSelected(i)}
                        style={{ ...S.listRow, ...(i === selected ? S.listRowActive : {}) }}
                      >
                        <span style={S.listRank}>{String(i + 1).padStart(2, "0")}</span>
                        <span style={S.listName}>{d.company.name}</span>
                        <span style={{ ...S.listScore, color: recColor(d.fit.recommendation) }}>
                          {d.fit.hard_failed ? "—" : d.fit.overall_score}
                        </span>
                      </button>
                    ))}
                  </div>
                </Panel>

                {/* selected detail */}
                {active && (
                  <Panel
                    title={active.company.name}
                    badge={active.fit.recommendation}
                    badgeColor={recColor(active.fit.recommendation)}
                  >
                    <div style={S.memo}>{active.memo}</div>

                    <div style={S.statRow}>
                      <Stat label="Revenue" v={fmtMoney(active.company.financials.revenue)} />
                      <Stat label="EBITDA*" v={fmtMoney(active.company.financials.ebitda)} />
                      <Stat label="Rev. growth" v={fmtPct(active.company.financials.revenue_growth)} />
                      <Stat label="Country" v={active.company.country} />
                    </div>

                    {radarData.length > 0 && (
                      <ResponsiveContainer width="100%" height={240}>
                        <RadarChart data={radarData} outerRadius="72%">
                          <PolarGrid stroke={C.line} />
                          <PolarAngleAxis dataKey="criterion" tick={{ fill: C.textDim, fontSize: 10 }} />
                          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                          <Radar dataKey="score" stroke={C.gold} fill={C.gold} fillOpacity={0.22} />
                        </RadarChart>
                      </ResponsiveContainer>
                    )}

                    <div style={S.criteria}>
                      {active.fit.criteria.map((c, i) => (
                        <div key={i} style={S.critRow}>
                          <span style={{ ...S.critDot, background: c.verdict === "pass" ? C.green : c.verdict === "fail" ? C.red : C.textFaint }} />
                          <span style={S.critName}>{c.name.replace(/_/g, " ")}</span>
                          <span style={S.critReason}>{c.reason}</span>
                        </div>
                      ))}
                    </div>
                    {active.company.source_urls?.length > 0 && (
                      <a href={active.company.source_urls[0]} target="_blank" rel="noreferrer" style={S.source}>
                        View SEC filing ↗
                      </a>
                    )}
                  </Panel>
                )}
              </div>
            </>
          )}
        </main>
      </div>
      <footer style={S.footer}>
        Deterministic scoring · LLM-assisted narrative · figures never model-generated
        <span style={S.footNote}>  *EBITDA approximated from net income for SEC-sourced filers</span>
      </footer>
    </div>
  );
}

/* ---- small components ---- */
const SectionLabel = ({ children }) => <div style={S.sectionLabel}>{children}</div>;

function Field({ label, v, onChange, step }) {
  return (
    <div style={S.field}>
      <label style={S.fieldLabel}>{label}</label>
      <input
        style={S.input}
        type="number"
        step={step}
        value={v ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
function Kpi({ label, value, tone }) {
  return (
    <div style={S.kpi}>
      <div style={{ ...S.kpiValue, color: tone }}>{value}</div>
      <div style={S.kpiLabel}>{label}</div>
    </div>
  );
}
function Stat({ label, v }) {
  return (
    <div style={S.stat}>
      <div style={S.statLabel}>{label}</div>
      <div style={S.statValue}>{v}</div>
    </div>
  );
}
function Panel({ title, badge, badgeColor, children, pad = true }) {
  return (
    <section style={S.panel}>
      <div style={S.panelHead}>
        <h3 style={S.panelTitle}>{title}</h3>
        {badge && <span style={{ ...S.badge, color: badgeColor, borderColor: badgeColor }}>{badge}</span>}
      </div>
      <div style={{ padding: pad ? "16px 18px" : 0 }}>{children}</div>
    </section>
  );
}

/* ---- styles ---- */
const GLOBAL = `
  @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Archivo:wght@300;400;500;600&display=swap');
  * { box-sizing: border-box; margin: 0; }
  body { background: ${C.ink}; }
  ::-webkit-scrollbar { width: 9px; height: 9px; }
  ::-webkit-scrollbar-thumb { background: ${C.line}; border-radius: 5px; }
  ::-webkit-scrollbar-track { background: ${C.ink}; }
  input:focus { outline: none; border-color: ${C.gold} !important; }
  @keyframes fade { from { opacity: 0; transform: translateY(6px);} to {opacity:1; transform:none;} }
`;

const S = {
  root: { minHeight: "100vh", background: `radial-gradient(1200px 600px at 80% -10%, #16343b 0%, ${C.ink} 55%)`, color: C.text, fontFamily: "Archivo, sans-serif", paddingBottom: 60 },
  header: { display: "flex", justifyContent: "space-between", alignItems: "flex-end", padding: "34px 40px 22px", borderBottom: `1px solid ${C.line}` },
  eyebrow: { fontSize: 10.5, letterSpacing: "0.32em", color: C.gold, fontWeight: 600, marginBottom: 8 },
  title: { fontFamily: "Fraunces, serif", fontSize: 38, fontWeight: 500, letterSpacing: "-0.01em", lineHeight: 1 },
  headerMeta: { textAlign: "right" },
  metaLabel: { display: "block", fontSize: 10, letterSpacing: "0.2em", color: C.textFaint },
  metaValue: { fontFamily: "Fraunces, serif", fontSize: 17, color: C.text },
  grid: { display: "grid", gridTemplateColumns: "300px 1fr", gap: 0 },
  rail: { borderRight: `1px solid ${C.line}`, padding: "24px 22px", minHeight: "calc(100vh - 160px)" },
  sectionLabel: { fontSize: 10.5, letterSpacing: "0.22em", color: C.textFaint, fontWeight: 600, marginBottom: 12, textTransform: "uppercase" },
  segmented: { display: "flex", border: `1px solid ${C.line}`, borderRadius: 7, overflow: "hidden" },
  segBtn: { flex: 1, padding: "9px 6px", background: "transparent", color: C.textDim, border: "none", fontSize: 12, fontFamily: "Archivo", cursor: "pointer", transition: "0.2s" },
  segBtnActive: { background: C.gold, color: C.ink, fontWeight: 600 },
  divider: { height: 1, background: C.line, margin: "22px 0" },
  fields: { display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 },
  field: {},
  fieldLabel: { display: "block", fontSize: 11, color: C.textDim, marginBottom: 5 },
  input: { width: "100%", background: C.panel, border: `1px solid ${C.line}`, borderRadius: 6, padding: "8px 10px", color: C.text, fontSize: 13, fontFamily: "Archivo", transition: "0.2s" },
  fileInput: { width: "100%", fontSize: 12, color: C.textDim },
  hint: { fontSize: 10.5, color: C.textFaint, marginTop: 6, lineHeight: 1.4 },
  runBtn: { width: "100%", marginTop: 22, padding: "13px", background: C.green, color: C.ink, border: "none", borderRadius: 7, fontSize: 13.5, fontWeight: 600, fontFamily: "Archivo", letterSpacing: "0.04em", cursor: "pointer", transition: "0.2s" },
  error: { color: C.red, fontSize: 12, marginTop: 12, lineHeight: 1.4 },
  main: { padding: "26px 40px" },
  kpiRow: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 24 },
  kpi: { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 9, padding: "16px 18px" },
  kpiValue: { fontFamily: "Fraunces, serif", fontSize: 30, fontWeight: 500, lineHeight: 1 },
  kpiLabel: { fontSize: 10.5, letterSpacing: "0.18em", color: C.textFaint, marginTop: 7, textTransform: "uppercase" },
  empty: { textAlign: "center", padding: "90px 20px", color: C.textFaint },
  emptyMark: { fontSize: 30, color: C.gold, marginBottom: 18, opacity: 0.6 },
  emptyText: { maxWidth: 380, margin: "0 auto", fontSize: 14, lineHeight: 1.6, color: C.textDim },
  panel: { background: C.panel, border: `1px solid ${C.line}`, borderRadius: 10, marginBottom: 20, animation: "fade 0.4s ease both" },
  panelHead: { display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 18px", borderBottom: `1px solid ${C.line}` },
  panelTitle: { fontFamily: "Fraunces, serif", fontSize: 17, fontWeight: 500 },
  badge: { fontSize: 10.5, letterSpacing: "0.08em", border: "1px solid", borderRadius: 20, padding: "4px 11px", fontWeight: 600 },
  detailGrid: { display: "grid", gridTemplateColumns: "270px 1fr", gap: 20 },
  list: { display: "flex", flexDirection: "column" },
  listRow: { display: "grid", gridTemplateColumns: "30px 1fr auto", alignItems: "center", gap: 8, padding: "13px 16px", background: "transparent", border: "none", borderBottom: `1px solid ${C.line}`, color: C.text, cursor: "pointer", textAlign: "left", fontFamily: "Archivo", transition: "0.15s" },
  listRowActive: { background: C.panel2 },
  listRank: { fontSize: 11, color: C.textFaint, fontVariantNumeric: "tabular-nums" },
  listName: { fontSize: 13 },
  listScore: { fontFamily: "Fraunces, serif", fontSize: 16, fontWeight: 600, fontVariantNumeric: "tabular-nums" },
  memo: { fontSize: 13.5, lineHeight: 1.65, color: C.text, marginBottom: 18 },
  statRow: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 12, marginBottom: 8, paddingBottom: 16, borderBottom: `1px solid ${C.line}` },
  stat: {},
  statLabel: { fontSize: 10, letterSpacing: "0.12em", color: C.textFaint, textTransform: "uppercase", marginBottom: 4 },
  statValue: { fontFamily: "Fraunces, serif", fontSize: 18, fontWeight: 500 },
  criteria: { marginTop: 6 },
  critRow: { display: "grid", gridTemplateColumns: "12px 130px 1fr", alignItems: "center", gap: 10, padding: "7px 0", fontSize: 12 },
  critDot: { width: 8, height: 8, borderRadius: "50%" },
  critName: { color: C.textDim, textTransform: "capitalize" },
  critReason: { color: C.text, fontSize: 12 },
  source: { display: "inline-block", marginTop: 14, fontSize: 12, color: C.gold, textDecoration: "none" },
  tooltip: { background: C.panel2, border: `1px solid ${C.line}`, borderRadius: 7, color: C.text, fontSize: 12 },
  footer: { textAlign: "center", marginTop: 30, fontSize: 11, color: C.textFaint, letterSpacing: "0.04em" },
  footNote: { color: C.textFaint, opacity: 0.7 },
};
