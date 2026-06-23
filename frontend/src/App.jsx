import React, { useEffect, useState } from 'react'
import { getFiles, getPreview, runReconcile } from './api.js'

const gbp = (n) =>
  n == null ? '—' : '£' + Number(n).toLocaleString('en-GB', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const fmtDay = (d) => (d ? `${d.slice(6, 8)} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+d.slice(4, 6) - 1]} ${d.slice(0, 4)}` : '')

const REVEAL = { raw: 1, timing: 3, fx: 4, rounding: 4, explained: 4, isa: 5, residual: 5 }
const NAV = [
  ['▦', 'Dashboard', true], ['⇄', 'Reconciliation', false],
  ['🗎', 'Files', false], ['!', 'Exceptions', false], ['⚙', 'Settings', false],
]

const catTotals = (cls) => {
  const t = { timing: 0, fx: 0, rounding: 0, residual: 0 }
  for (const c of cls || []) if (c.type in t) t[c.type] += Number(c.amount) || 0
  return t
}

function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="brand"><span className="dot">R</span> ReconAgent</div>
      <nav className="nav">{NAV.map(([ic, l, a]) => <a key={l} className={a ? 'active' : ''}><span className="ico">{ic}</span>{l}</a>)}</nav>
      <div className="side-foot">Reconciliation Exception Agent</div>
    </aside>
  )
}

const Kpi = ({ lbl, val, hint, accent }) => (
  <div className={`card kpi ${accent ? 'accent' : ''}`}>
    <div className="lbl">{lbl}</div><div className="val">{val}</div>{hint && <div className="hint">{hint}</div>}
  </div>
)

function FileCard({ f, onPreview, reconciledDay, catchUpDay }) {
  const side = f.side === 'Visa' ? 'visa' : 'thredd'
  const role = f.day === reconciledDay ? 'settlement day' : f.day === catchUpDay ? 'catch-up' : null
  return (
    <div className="file">
      <div className="row1"><span className="nm">{f.name}</span><span className={`tag ${side}`}>{f.side}</span></div>
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
    { k: 'True break → analyst', v: residual, c: '#f6c344', res: true, from: REVEAL.residual },
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
            <td><b>{c.label}</b>{c.arn && <div className="mono">{c.arn}</div>}</td>
            <td>{c.explanation}</td><td className="amt">{gbp(c.amount)}</td>
            <td><span className={`pill ${c.status}`}>{c.status === 'routed' ? 'escalated' : c.status}</span></td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function PreviewModal({ name, data, onClose }) {
  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="hd"><b>{name}</b><button className="x" onClick={onClose}>×</button></div>
        <div className="bd">
          {!data && <div className="empty">Loading…</div>}
          {data?.type === 'json' && <pre className="raw">{JSON.stringify(data.data, null, 2)}</pre>}
          {data?.raw_sample && (<><div className="note" style={{ marginTop: 0, marginBottom: 6 }}>Raw BASE II (decoded below):</div><div className="raw">{data.raw_sample.join('\n')}</div></>)}
          {data?.rows && (
            <table className="x">
              <thead><tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
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

  useEffect(() => { getFiles().then(setMeta).catch((e) => console.error(e)) }, [])

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
      <Sidebar />
      <main className="main">
        <div className="topbar">
          <div>
            <h1>Reconciliation — Unreconciled Day</h1>
            <div className="sub">{meta ? <>Settlement day <b>{fmtDay(meta.reconciled_day)}</b> · SRE {meta.sre} · catch-up file {fmtDay(meta.catch_up_day)}</> : 'Loading…'}</div>
          </div>
          <div className="right">
            <span className={`badge ${running || (result && !hasAgent) || routed ? 'warn' : ''}`}>
              {running && <span className="spin-d" style={{ marginRight: 8, verticalAlign: -1 }} />}{badge}
            </span>
            <button className="btn primary" onClick={handleRun} disabled={running}>
              {running ? <><span className="spin" />Running…</> : 'Run reconciliation'}
            </button>
          </div>
        </div>

        <div className="grid-kpi">
          <Kpi lbl="Raw difference" val={showRaw ? gbp(t.raw_difference) : '—'}
               hint={showRaw ? `Visa net ${gbp(t.visa_net_settlement)} vs Thredd ${gbp(t.thredd_day1_sum)}` : 'Run to compute'} />
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
              <h2>Files received <span className="muted">2 from Visa · 2 from Thredd</span></h2>
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
                  {ag.steps.map((s, i) => {
                    const isDone = i < visible, isDoing = i === doing
                    return (
                      <div key={s.step} className={`step ${isDone ? 'on' : isDoing ? 'doing' : 'pending'}`}>
                        <div className="num">{isDone ? '✓' : isDoing ? <span className="spin-d" /> : s.step}</div>
                        <div><div className="tl">{s.title}</div>
                          {isDone && <div className="dt">{s.detail}</div>}
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
      </main>

      {preview && <PreviewModal name={preview.name} data={preview.data} onClose={() => setPreview(null)} />}
    </div>
  )
}
