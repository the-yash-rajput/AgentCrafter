import { useState } from 'react'
import { X, Play, ChevronDown, ChevronRight, CheckCircle, XCircle, Loader } from 'lucide-react'
import { runAgent } from '../../api/client'
import toast from 'react-hot-toast'
import Editor from '@monaco-editor/react'

const StatusBadge = ({ status }) => {
  const map = {
    success: { color: '#10b981', label: 'Success' },
    failed: { color: '#ef4444', label: 'Failed' },
    running: { color: '#6366f1', label: 'Running' },
    pending: { color: '#64748b', label: 'Pending' },
  }
  const s = map[status] || map.pending
  return (
    <span className="px-2 py-0.5 rounded-full text-xs font-mono font-semibold"
          style={{ background: `${s.color}22`, color: s.color, border: `1px solid ${s.color}44` }}>
      {s.label}
    </span>
  )
}

const SnapshotItem = ({ snapshot, index }) => {
  const [open, setOpen] = useState(false)
  const typeColor = snapshot.node_type === 'llm_call' ? '#7c3aed' : '#0ea5e9'

  return (
    <div className="rounded-lg overflow-hidden" style={{ border: '1px solid var(--border2)' }}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-3 px-4 py-3 text-left hover:opacity-80"
        style={{ background: 'var(--surface2)' }}
      >
        <div className="w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono font-bold"
             style={{ background: `${typeColor}22`, color: typeColor }}>
          {index + 1}
        </div>
        <div className="flex-1">
          <p className="text-sm font-semibold text-white">{snapshot.node_name}</p>
          <p className="text-xs font-mono" style={{ color: typeColor }}>{snapshot.node_type}</p>
        </div>
        <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
          {new Date(snapshot.timestamp).toLocaleTimeString()}
        </p>
        {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
      </button>

      {open && (
        <div className="grid grid-cols-2 gap-0" style={{ borderTop: '1px solid var(--border)' }}>
          <div className="p-3" style={{ borderRight: '1px solid var(--border)' }}>
            <p className="text-xs font-mono mb-2" style={{ color: 'var(--text-muted)' }}>State Before</p>
            <pre className="text-xs overflow-auto max-h-40 rounded p-2" style={{ background: 'var(--bg)', color: '#94a3b8', fontFamily: 'JetBrains Mono, monospace' }}>
              {JSON.stringify(snapshot.state_before, null, 2)}
            </pre>
          </div>
          <div className="p-3">
            <p className="text-xs font-mono mb-2" style={{ color: 'var(--text-muted)' }}>State After</p>
            <pre className="text-xs overflow-auto max-h-40 rounded p-2" style={{ background: 'var(--bg)', color: '#a7f3d0', fontFamily: 'JetBrains Mono, monospace' }}>
              {JSON.stringify(snapshot.state_after, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

export const RunModal = ({ agent, onClose }) => {
  const [inputJson, setInputJson] = useState('{\n  \n}')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)

  const handleRun = async () => {
    let inputData = {}
    try {
      inputData = JSON.parse(inputJson)
    } catch (e) {
      toast.error('Invalid JSON input')
      return
    }

    setRunning(true)
    setResult(null)
    try {
      const run = await runAgent(agent.id, inputData)
      setResult(run)
      if (run.status === 'success') toast.success('Run completed successfully!')
      else toast.error('Run failed')
    } catch (e) {
      const detail = e.response?.data?.detail
      toast.error(typeof detail === 'object' ? JSON.stringify(detail) : (detail || 'Run failed'))
    }
    setRunning(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.8)' }}>
      <div
        className="w-[900px] max-h-[85vh] flex flex-col rounded-2xl fade-in"
        style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#6366f122', border: '1px solid #6366f144' }}>
              <Play size={14} style={{ color: '#6366f1' }} />
            </div>
            <div>
              <h2 className="text-base font-semibold text-white">Run Agent: {agent.name}</h2>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Execute the workflow with input data</p>
            </div>
          </div>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Input */}
          <div className="w-64 flex flex-col border-r" style={{ borderColor: 'var(--border)' }}>
            <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
              <p className="text-xs font-mono uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>Input JSON</p>
            </div>
            <div className="flex-1">
              <Editor
                height="100%"
                defaultLanguage="json"
                value={inputJson}
                onChange={v => setInputJson(v)}
                theme="vs-dark"
                options={{ minimap: { enabled: false }, fontSize: 12, lineNumbers: 'off' }}
              />
            </div>
            <div className="p-4">
              <button
                onClick={handleRun}
                disabled={running}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all"
                style={{ background: running ? '#4338ca' : '#6366f1', color: '#fff' }}
              >
                {running ? <><Loader size={14} className="animate-spin" /> Running...</> : <><Play size={14} /> Run</>}
              </button>
            </div>
          </div>

          {/* Output */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {!result && !running && (
              <div className="flex-1 flex items-center justify-center">
                <p className="text-sm" style={{ color: 'var(--text-muted)' }}>Set input JSON and click Run</p>
              </div>
            )}
            {running && (
              <div className="flex-1 flex items-center justify-center">
                <div className="text-center">
                  <Loader size={32} className="animate-spin mx-auto mb-3" style={{ color: '#6366f1' }} />
                  <p className="text-sm text-white">Executing workflow...</p>
                </div>
              </div>
            )}
            {result && (
              <div className="flex-1 overflow-y-auto">
                {/* Status bar */}
                <div className="flex items-center gap-3 px-5 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
                  <StatusBadge status={result.status} />
                  <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    {(result.state_snapshots || []).length} steps
                  </p>
                  {result.completed_at && (
                    <p className="text-xs font-mono ml-auto" style={{ color: 'var(--text-muted)' }}>
                      Completed {new Date(result.completed_at).toLocaleTimeString()}
                    </p>
                  )}
                </div>

                {result.error && (
                  <div className="mx-5 mt-4 p-3 rounded-lg" style={{ background: '#ef444422', border: '1px solid #ef4444' }}>
                    <p className="text-xs font-mono" style={{ color: '#ef4444' }}>{result.error}</p>
                  </div>
                )}

                {/* Final output */}
                <div className="px-5 py-4">
                  <p className="text-xs font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>Final Output</p>
                  <pre className="text-xs p-3 rounded-lg overflow-auto max-h-36"
                       style={{ background: 'var(--bg)', color: '#a7f3d0', fontFamily: 'JetBrains Mono, monospace', border: '1px solid var(--border2)' }}>
                    {JSON.stringify(result.output_data, null, 2)}
                  </pre>
                </div>

                {/* Snapshots */}
                {(result.state_snapshots || []).length > 0 && (
                  <div className="px-5 pb-5">
                    <p className="text-xs font-mono uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
                      Step-by-step Trace
                    </p>
                    <div className="space-y-2">
                      {result.state_snapshots.map((snap, i) => (
                        <SnapshotItem key={i} snapshot={snap} index={i} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
