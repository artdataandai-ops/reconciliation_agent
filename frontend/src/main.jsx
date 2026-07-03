import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.jsx'
import './styles.css'

// Turn a render crash into a readable message instead of a blank white screen.
class ErrorBoundary extends React.Component {
  constructor(p) { super(p); this.state = { err: null } }
  static getDerivedStateFromError(err) { return { err } }
  componentDidCatch(err, info) { console.error('App crashed:', err, info) }
  render() {
    if (this.state.err) return (
      <div style={{ padding: 24, fontFamily: 'ui-monospace,monospace', color: '#f0a285', background: '#0f1115', minHeight: '100vh' }}>
        <h2 style={{ color: '#e6e8eb', marginTop: 0 }}>The app hit a runtime error</h2>
        <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13 }}>{String(this.state.err?.stack || this.state.err)}</pre>
      </div>
    )
    return this.props.children
  }
}

createRoot(document.getElementById('root')).render(
  <ErrorBoundary><App /></ErrorBoundary>
)
