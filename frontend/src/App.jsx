import React, { useEffect, useState } from 'react'
import { getFiles, getActivity, getPreview, runReconcile } from './api.js'

const gbp = (n) =>
  n == null ? '—' : '£' + Number(n).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
// Multi-currency formatter for the Activity overview + per-day detail (the dashboard stays GBP via gbp()).
const CCY = { GBP: ['£', 2], EUR: ['€', 2], USD: ['US$', 2], AUD: ['A$', 2], JPY: ['¥', 0], NZD: ['NZ$', 2], SGD: ['S$', 2] }
const money = (n, ccy) => n == null ? '—' : (CCY[ccy]?.[0] ?? '') +
  Number(n).toLocaleString('en-GB', { minimumFractionDigits: CCY[ccy]?.[1] ?? 2, maximumFractionDigits: CCY[ccy]?.[1] ?? 2 })
const fmtDay = (d) => (d ? `${d.slice(6, 8)} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+d.slice(4, 6) - 1]} ${d.slice(0, 4)}` : '')
// display-only: never show the processor's brand in file names (real name is still used for fetch)
const maskName = (n) => (n ? n.replace('THREDD_TXN_REPORT', 'PROCESSOR_TXN_REPORT') : n)

const REVEAL = { raw: 1, timing: 3, fx: 4, rounding: 4, explained: 4, isa: 5, residual: 5 }
const NAV = [
  ['▤', 'Activity Reconciliation', 'activity'],
  ['▦', 'Reconciliation Agent', 'dashboard'], ['⇄', 'Transactions', 'reconciliation'],
]

const catTotals = (cls) => {
  const t = { timing: 0, fx: 0, rounding: 0, residual: 0 }
  for (const c of cls || []) if (c.type in t) t[c.type] += Number(c.amount) || 0
  return t
}

// The agent is an LLM, so its output shape varies. Normalize defensively:
//  - a step may arrive as {step,title,detail} OR as a plain "Title: detail" string
//  - a classification item may omit `label` → fall back to a name derived from its `type`
const TYPE_LABEL = { timing: 'Timing', fx: 'FX rate-timing', rounding: 'Rounding', isa: 'Scheme ISA', residual: 'Residual break' }
const exLabel = (c) => c.label || TYPE_LABEL[c.type] || 'Difference'
function normStep(s, i) {
  if (s && typeof s === 'object') return { step: s.step ?? i + 1, title: s.title || `Step ${i + 1}`, detail: s.detail || '' }
  const str = String(s ?? '')
  const c = str.indexOf(':')
  return (c > 0 && c < 42)
    ? { step: i + 1, title: str.slice(0, c).trim(), detail: str.slice(c + 1).trim() }
    : { step: i + 1, title: `Step ${i + 1}`, detail: str }
}

function Sidebar({ view, onNavigate, theme, onToggleTheme }) {
  return (
    <aside className="sidebar">
      <div className="brand"><span className="dot">R</span>
        <div className="brand-text"><div className="brand-name">Recon Agent</div><div className="brand-desc">Reconciliation Agent</div></div>
      </div>
      <nav className="nav">{NAV.map(([ic, l, key]) => (
        <a key={l} className={key && view === key ? 'active' : ''}
           onClick={key ? () => onNavigate(key) : undefined}>
          <span className="ico">{ic}</span>{l}
        </a>
      ))}</nav>
      <button className="theme-toggle" onClick={onToggleTheme}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
        <span className="ico">{theme === 'dark' ? '☀' : '☾'}</span>
        {theme === 'dark' ? 'Light theme' : 'Dark theme'}
      </button>
      <div className="side-foot">Art Technology and Software</div>
    </aside>
  )
}

const Kpi = ({ lbl, val, hint, accent }) => (
  <div className={`card kpi ${accent ? 'accent' : ''}`}>
    <div className="lbl">{lbl}</div><div className="val">{val}</div>{hint && <div className="hint">{hint}</div>}
  </div>
)

function FileCard({ f, onPreview, reconciledDay, catchUpDay }) {
  const side = f.side === 'Visa' ? 'visa' : 'processor'
  const role = f.day === reconciledDay ? 'settlement day' : f.day === catchUpDay ? 'catch-up' : null
  return (
    <div className="file">
      <div className="row1"><span className="nm">{maskName(f.name)}</span><span className={`tag ${side}`}>{f.side}</span></div>
      <div className="meta">{f.kind} · {fmtDay(f.day)}{role ? ` (${role})` : ''}</div>
      <div className="row1" style={{ marginTop: 10 }}>
        <span className="rcv">✓ received · {f.records} records</span>
        <span className="lnk" onClick={() => onPreview(f.name)}>Preview</span>
      </div>
    </div>
  )
}

function Waterfall({ totals, residual, visible }) {
  const all = [
    { k: 'Timing', v: totals.timing, c: '#6b7280', from: REVEAL.timing },
    { k: 'FX rate-timing', v: totals.fx, c: '#9ca3af', from: REVEAL.fx },
    { k: 'Rounding', v: Math.abs(totals.rounding), c: '#cbd5e1', from: REVEAL.rounding },
    { k: 'True break → analyst', v: residual, c: '#FEC422', res: true, from: REVEAL.residual },
  ]
  const total = all.reduce((s, x) => s + Math.abs(x.v), 0) || 1
  const shown = all.filter((s) => visible >= s.from)
  return (
    <div>
      <div className="wf-bar">
        {shown.map((s) => (
          <div key={s.k} className="wf-seg" style={{ width: `${(Math.abs(s.v) / total) * 100}%`, background: s.c, color: s.res ? '#3a2f00' : '#fff' }}>
            {Math.abs(s.v) / total > 0.08 ? gbp(s.v) : ''}
          </div>
        ))}
      </div>
      <div className="wf-legend">
        {shown.map((s) => (
          <div key={s.k} className={`wf-leg ${s.res ? 'res' : ''}`}>
            <span className="sw" style={{ background: s.c }} />{s.k}<span className="amt">{gbp(s.v)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Exceptions({ rows, visible }) {
  const shown = rows.filter((c) => visible >= (REVEAL[c.type] ?? 5))
  return (
    <table className="x">
      <thead><tr><th>Type</th><th>Detail</th><th style={{ textAlign: 'right' }}>Amount</th><th>Status</th></tr></thead>
      <tbody>
        {shown.map((c, i) => (
          <tr key={i} className={c.type === 'residual' ? 'res' : ''}>
            <td><b>{exLabel(c)}</b>{c.arn && <div className="mono">{c.arn}</div>}</td>
            <td>{c.explanation}</td><td className="amt">{gbp(c.amount)}</td>
            <td><span className={`pill ${c.status}`}>{c.status === 'routed' ? 'escalated' : c.status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const TXN_STATUS = {
  matched:       { label: 'Reconciled',             bucket: 'reconciled' },
  fx:            { label: 'Reconciled · fx',         bucket: 'reconciled' },
  timing:        { label: 'Reconciled · timing',     bucket: 'reconciled' },
  residual:      { label: 'Unreconciled',            bucket: 'break' },
  platform_only: { label: 'Unreconciled · platform', bucket: 'break' },
}
const svc = (region) => (region === 'INTL' ? 'International' : region === 'NAT' ? 'National' : '—')
// Friendlier headers for the file-preview tables (data keys are unchanged)
const PREVIEW_LABELS = { settlement_amt: 'Net Processed', settle_gbp: 'Net Settlement' }

// Per-day transaction detail. Reached by clicking an Activity row (or the sidebar).
//  - a reconciled history day → its mock transactions (amounts in that day's settlement currency)
//  - the real GBP day (selectedDay.real, or no selection) → the engine's transactions from the run
function ReconciliationView({ result, selectedDay, onBack }) {
  const [filter, setFilter] = useState('all')
  const isMock = selectedDay && !selectedDay.real
  const txns = isMock ? selectedDay.transactions : result?.findings?.transactions
  const displayCcy = isMock ? selectedDay.currency : 'GBP'
  const crumb = onBack && <span className="crumb" onClick={onBack}>← Back to Activity</span>
  const title = selectedDay
    ? <>Transactions <span className="muted">{fmtDay(selectedDay.date)} · {selectedDay.currency} · {selectedDay.service}</span></>
    : <>Transactions</>

  if (!txns) return (
    <section className="card panel">{crumb}<h2>{title}</h2>
      <div className="empty">Click <b>Run reconciliation</b> on the Dashboard to list every transaction as reconciled or unreconciled.</div>
    </section>
  )
  const rows = txns.filter((t) => filter === 'all' || TXN_STATUS[t.status]?.bucket === filter)
  const reconciled = txns.filter((t) => TXN_STATUS[t.status]?.bucket === 'reconciled').length
  const broke = txns.length - reconciled
  return (
    <section className="card panel">{crumb}
      <h2>{title}<span className="muted">{txns.length} txns · {reconciled} reconciled · {broke} unreconciled</span></h2>
      {isMock && (
        <div className="ok-banner">✓ Auto-cleared — Net Settlement = Net Processed, gap {money(0, displayCcy)}. Nothing to explain.</div>
      )}
      <div className="txn-filter">
        {[['all', 'All'], ['reconciled', 'Reconciled'], ['break', 'Unreconciled']].map(([f, lbl]) => (
          <button key={f} className={`chip ${filter === f ? 'on' : ''}`} onClick={() => setFilter(f)}>{lbl}</button>
        ))}
      </div>
      <table className="x">
        <thead><tr>
          <th>Status</th><th>Merchant</th>
          <th style={{ textAlign: 'right' }}>Net Settlement</th>
          <th style={{ textAlign: 'right' }}>Gap</th>
          <th style={{ textAlign: 'right' }}>Net Processed</th>
          <th>Ccy</th><th>Clearing</th>
        </tr></thead>
        <tbody>
          {rows.map((t, i) => {
            const s = TXN_STATUS[t.status] || { label: t.status, bucket: '' }
            return (
              <tr key={i} className={s.bucket === 'break' ? 'res' : ''}>
                <td><span className={`pill ${t.status}`}>{s.label}</span></td>
                <td><b>{t.merchant}</b>{t.arn && <div className="mono">{t.arn}</div>}</td>
                <td className="amt">{money(t.visa_amount, displayCcy)}</td>
                <td className="amt">{money(t.gap, displayCcy)}</td>
                <td className="amt">{t.thredd_amount == null ? '—' : money(t.thredd_amount, displayCcy)}</td>
                <td>{t.source_ccy || '—'}</td>
                <td>{svc(t.region)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

// Activity Reconciliation overview: recent settlement records, one row per (date × currency).
// Every row is clickable → its per-day transactions. Only the real GBP row is Unreconciled; after a
// run it reflects the deterministic residual ("Residual → analyst · <amount> unexplained").
function ActivityView({ rows, result, onOpenDay }) {
  const [filter, setFilter] = useState('all')
  if (!rows) return (
    <section className="card panel"><div className="empty">Loading…</div></section>
  )
  const ranDay = result?.findings?.dates?.reconciled_day
  const residual = result?.findings?.facts?.residual?.total
  const shown = rows.filter((r) => filter === 'all'
    || (filter === 'break' ? r.status === 'unreconciled' : r.status === 'reconciled'))
  const nBreak = rows.filter((r) => r.status === 'unreconciled').length
  return (
    <section className="card panel">
      <h2><span className="muted">{rows.length} settlement records · {nBreak} unreconciled</span></h2>
      <div className="txn-filter">
        {[['all', 'All'], ['reconciled', 'Reconciled'], ['break', 'Unreconciled']].map(([f, lbl]) => (
          <button key={f} className={`chip ${filter === f ? 'on' : ''}`} onClick={() => setFilter(f)}>{lbl}</button>
        ))}
      </div>
      <table className="x">
        <thead><tr>
          <th>Status</th><th>Settlement Date</th>
          <th style={{ textAlign: 'right' }}>Net Settlement</th>
          <th style={{ textAlign: 'right' }}>Gap</th>
          <th style={{ textAlign: 'right' }}>Net Processed</th>
          <th>Currency</th><th>Settlement Service</th>
        </tr></thead>
        <tbody>
          {shown.map((r, i) => {
            const un = r.status === 'unreconciled'
            const ran = un && r.real && result && ranDay === r.date   // residual revealed after the run
            return (
              <tr key={i} className={`act-click ${un ? 'res' : ''}`} onClick={() => onOpenDay(r)}>
                <td>
                  <span className={`pill ${un ? (ran ? 'routed' : 'residual') : 'matched'}`}>
                    {un ? (ran ? 'Residual → analyst' : 'Unreconciled') : 'Reconciled'}
                  </span>
                </td>
                <td>{fmtDay(r.date)}</td>
                <td className="amt">{money(r.net_settlement, r.currency)}</td>
                <td className="amt">{money(r.gap, r.currency)}
                  {ran && <div className="sub-res">{money(residual, r.currency)} unexplained</div>}
                </td>
                <td className="amt">{money(r.net_processed, r.currency)}</td>
                <td>{r.currency}</td>
                <td>{r.service}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}

function PreviewModal({ name, data, onClose }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="hd"><b>{maskName(name)}</b><button className="x" onClick={onClose}>×</button></div>
        <div className="bd">
          {!data && <div className="empty">Loading…</div>}
          {data?.type === 'json' && <pre className="raw">{JSON.stringify(data.data, null, 2)}</pre>}
          {data?.raw_sample && (<><div className="note" style={{ marginTop: 0, marginBottom: 6 }}>Raw BASE II (decoded below):</div><div className="raw">{data.raw_sample.join('\n')}</div></>)}
          {data?.rows && (
            <table className="x">
              <thead><tr>{data.columns.map((c) => <th key={c}>{PREVIEW_LABELS[c] ?? c}</th>)}</tr></thead>
              <tbody>{data.rows.map((r, i) => <tr key={i}>{data.columns.map((c) => <td key={c} className={typeof r[c] === 'number' ? 'amt' : ''}>{String(r[c] ?? '')}</td>)}</tr>)}</tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

export default function App() {
  const [meta, setMeta] = useState(null)
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [visible, setVisible] = useState(0)
  const [doing, setDoing] = useState(-1)
  const [preview, setPreview] = useState(null)
  const [view, setView] = useState('activity')
  const [activity, setActivity] = useState(null)
  const [selectedDay, setSelectedDay] = useState(null)
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')

  useEffect(() => {
    getFiles().then(setMeta).catch((e) => console.error(e))
    getActivity().then((d) => setActivity(d.days)).catch((e) => console.error(e))
  }, [])
  // Click a settlement row: the real GBP break opens the Dashboard (run the agent);
  // a reconciled currency opens its per-day transactions in the Reconciliation view.
  const openDay = (row) => { setSelectedDay(row); setView(row.real ? 'dashboard' : 'reconciliation') }
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  async function handleRun() {
    setRunning(true); setResult(null); setVisible(0); setDoing(-1)
    let data
    try { data = await runReconcile() } catch (e) { setRunning(false); alert('Reconcile failed: ' + e.message); return }
    setResult(data)
    if (!data.agent) { setRunning(false); return }   // no agent → numbers only, no animation
    const n = data.agent.steps.length
    let i = 0
    const step = () => {
      if (i >= n) { setDoing(-1); setRunning(false); return }
      setDoing(i)
      setTimeout(() => { setVisible(i + 1); i += 1; setTimeout(step, 240) }, 720)
    }
    setTimeout(step, 300)
  }

  async function openPreview(name) {
    setPreview({ name, data: null })
    try { setPreview({ name, data: await getPreview(name) }) }
    catch (e) { setPreview({ name, data: { type: 'json', data: { error: e.message } } }) }
  }

  const fnd = result?.findings
  const t = fnd?.totals
  const ag = result?.agent
  const hasAgent = !!ag
  const v = visible
  const ct = hasAgent ? catTotals(ag.classification) : null
  const residualTotal = fnd?.facts?.residual?.total
  const explained = ct ? ct.timing + ct.fx + ct.rounding : null
  const isaItem = hasAgent ? ag.classification.find((c) => c.type === 'isa') : null
  const routed = ag?.routing?.action === 'route_to_analyst'
  const tickets = ag?.routing?.escalation?.tickets || []
  const done = hasAgent && v >= ag.steps.length

  // neutral backend observations (shown even without the agent)
  const matched = t?.thredd_day1_count
  const nextDay = fnd?.facts?.timing?.items?.length
  const schemeOnly = fnd?.facts?.residual?.items?.length

  const showRaw = result && (!hasAgent || v >= REVEAL.raw)
  const badge = running ? 'Agent running…'
    : result ? (hasAgent ? (routed ? 'Residual → analyst' : 'Auto-cleared') : 'Numbers ready · agent not connected')
    : 'Files received · awaiting run'

  return (
    <div className="app">
      <Sidebar view={view} onNavigate={setView} theme={theme}
               onToggleTheme={() => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))} />
      <main className="main">
        <div className="topbar">
          <div>
            {view === 'activity' && <>
              <h1>Activity Reconciliation</h1>
              <div className="sub">{meta ? <>Recent settlement activity</> : 'Loading…'}</div>
            </>}
            {view === 'dashboard' && <>
              <h1>Daily Settlement Reconciliation</h1>
              <div className="sub">{meta ? <>Settlement day <b>{fmtDay(meta.reconciled_day)}</b> · catch-up file {fmtDay(meta.catch_up_day)}</> : 'Loading…'}</div>
            </>}
            {view === 'reconciliation' && <>
              <h1>Transaction Detail</h1>
              <div className="sub">{selectedDay ? <>{fmtDay(selectedDay.date)} · {selectedDay.currency} · {selectedDay.service}</> : 'Per-day transactions'}</div>
            </>}
          </div>
          {view === 'dashboard' && (
            <div className="right">
              {!running && <span className={`badge ${(result && !hasAgent) || routed ? 'warn' : ''}`}>{badge}</span>}
              <button className="btn primary" onClick={handleRun} disabled={running}>
                {running ? <><span className="spin" />Running…</> : 'Run reconciliation'}
              </button>
            </div>
          )}
        </div>

        {view === 'activity' && <ActivityView rows={activity} result={result} onOpenDay={openDay} />}

        {view === 'dashboard' && (<>
        <div className="grid-kpi">
          <Kpi lbl="Raw difference" val={showRaw ? gbp(t.raw_difference) : '—'}
               hint={showRaw ? `Visa net ${gbp(t.visa_net_settlement)} vs Processor ${gbp(t.thredd_day1_sum)}` : 'Run to compute'} />
          <Kpi lbl="Explained" val={hasAgent && v >= REVEAL.explained ? gbp(explained) : '—'}
               hint={result && !hasAgent ? 'needs agent' : (hasAgent && v >= REVEAL.explained ? 'timing + FX + rounding' : '—')} />
          <Kpi lbl="ISA confirmed" val={hasAgent && v >= REVEAL.isa ? (isaItem?.status === 'confirmed' ? '✓ equal' : 'review') : '—'}
               hint={result && !hasAgent ? 'needs agent' : '—'} />
          <Kpi lbl="Residual → analyst" val={hasAgent && v >= REVEAL.residual ? gbp(residualTotal) : '—'}
               hint={result && !hasAgent ? 'needs agent' : (hasAgent && v >= REVEAL.residual ? (routed ? `${schemeOnly} true break${tickets[0] ? ' · ' + tickets[0].key : ''}` : 'none — auto-clear') : '—')} accent />
        </div>

        <div className="cols">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <section className="card panel">
              <h2>Files received <span className="muted">2 from Visa · 2 from Processor</span></h2>
              {meta ? <div className="files">{meta.files.map((file) => <FileCard key={file.name} f={file} onPreview={openPreview} reconciledDay={meta.reconciled_day} catchUpDay={meta.catch_up_day} />)}</div> : <div className="empty">Loading files…</div>}
              <div className="note">In production these arrive automatically on sFTP and the agent triggers when all are present. Here: pre-loaded, run on demand.</div>
            </section>

            {result && (
              <section className="card panel">
                <h2>Difference breakdown <span className="muted">{gbp(t.raw_difference)} raw</span></h2>
                {hasAgent ? (
                  v >= REVEAL.timing
                    ? <Waterfall totals={ct} residual={residualTotal} visible={v} />
                    : <div className="empty">Agent classifying…</div>
                ) : (
                  <div className="backend-find">
                    <div className="bf-row"><span>Raw gap located</span><b>{gbp(t.raw_difference)}</b></div>
                    <div className="bf-row"><span>Matched both sides</span><b>{matched}</b></div>
                    <div className="bf-row"><span>Present only in next-day file</span><b>{nextDay}</b></div>
                    <div className="bf-row"><span>Present only on Visa side</span><b>{schemeOnly}</b></div>
                    <div className="note disconnect">🔌 The backend located <i>where</i> the differences are. Connect the
                      AI agent to classify them (timing / FX / rounding / scheme-fee / true break), explain each, and decide routing.</div>
                  </div>
                )}
              </section>
            )}

            {hasAgent && v >= REVEAL.timing && (
              <section className="card panel">
                <h2>Exceptions <span className="muted">classified as the agent works</span></h2>
                <Exceptions rows={ag.classification} visible={v} />
              </section>
            )}
          </div>

          <section className="card panel">
            <h2>Agent run log {result && <span className="muted">{hasAgent ? 'connected' : 'not connected'}</span>}</h2>
            {!result && !running && <div className="empty">Click <b>Run reconciliation</b> to let the agent walk the 5 steps.</div>}

            {result && !hasAgent && (
              <div className="disconnect-box">
                {result.agent_connected ? (
                  <>
                    <div className="headline">⚠ Agent call failed</div>
                    The agent is <b>configured</b>, but the call didn't return a usable result — check the
                    endpoint URL / API key / agent ID, then run again.
                    {result.agent_error && <div className="err">{result.agent_error}</div>}
                  </>
                ) : (
                  <>
                    <div className="headline">🔌 AI agent not connected</div>
                    The backend computed the numbers and located the differences — but the <b>interpretation</b> is the
                    agent's job. Connect the AI agent (set the API key and agent ID in
                    <code>backend/.env</code>) to classify, explain, and route.
                  </>
                )}
              </div>
            )}

            {hasAgent && (
              <>
                <div className="steps">
                  {ag.steps.map((raw, i) => {
                    const s = normStep(raw, i)
                    const isDone = i < visible, isDoing = i === doing
                    return (
                      <div key={i} className={`step ${isDone ? 'on' : isDoing ? 'doing' : 'pending'}`}>
                        <div className="num">{isDone ? '✓' : isDoing ? <span className="spin-d" /> : s.step}</div>
                        <div><div className="tl">{s.title}</div>
                          {isDone && s.detail && <div className="dt">{s.detail}</div>}
                          {isDoing && <div className="dt"><i>analysing…</i></div>}</div>
                      </div>
                    )
                  })}
                </div>
                {done && (
                  <div className="narr">
                    <div className="headline">{ag.headline}</div>
                    {ag.narrative}
                    {tickets.length > 0 && (
                      <div className="esc">🎫 Escalated to Jira:
                        {tickets.map((tk) => (
                          <a key={tk.key} className="ticket" href={tk.url} target="_blank" rel="noreferrer">{tk.key} ↗</a>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </section>
        </div>
        </>)}

        {view === 'reconciliation' && <ReconciliationView result={result} selectedDay={selectedDay} onBack={() => setView('activity')} />}
      </main>

      {preview && <PreviewModal name={preview.name} data={preview.data} onClose={() => setPreview(null)} />}
    </div>
  )
}
