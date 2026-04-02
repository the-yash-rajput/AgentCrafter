import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Play, Database, Download, Upload, Copy, CheckCircle, AlertCircle, ChevronDown, Sparkles, Undo2 } from 'lucide-react'
import { updateAgent, validateAgent, exportAgent } from '../../api/client'
import { useGraphStore } from '../../hooks/useGraphStore'
import toast from 'react-hot-toast'

export const TopBar = ({
  agent,
  isDirty,
  onSchemaEdit,
  onRun,
  onRearrangeGraph,
  onUndoLayout,
  canUndoLayout = false,
  isRearranging = false,
}) => {
  const navigate = useNavigate()
  const { setAgent, latestRun } = useGraphStore()
  const [saving, setSaving] = useState(false)
  const [validation, setValidation] = useState(null)
  const [showMenu, setShowMenu] = useState(false)
  const hasEntryNode = Boolean(agent?.entry_node)
  const latestRunId = latestRun?.id ?? latestRun?.run_id ?? null

  const handleSaveAgent = async () => {
    if (!agent) return
    setSaving(true)
    try {
      const updated = await updateAgent(agent.id, {
        name: agent.name,
        status: 'active',
      })
      setAgent(updated)
      toast.success('Agent saved')
    } catch (e) {
      toast.error('Save failed')
    }
    setSaving(false)
  }

  const handleValidate = async () => {
    try {
      const result = await validateAgent(agent.id)
      setValidation(result)
      if (result.valid) toast.success(`Valid graph — ${result.node_count} nodes, ${result.edge_count} edges`)
      else toast.error(`${result.errors.length} validation error(s)`)
    } catch (e) {
      toast.error('Validation failed')
    }
  }

  const handleExport = async () => {
    try {
      const data = await exportAgent(agent.id)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${agent.name}.json`
      a.click()
      toast.success('Exported')
    } catch (e) {
      toast.error('Export failed')
    }
  }

  const statusColors = { draft: '#64748b', active: '#10b981', archived: '#f59e0b' }

  return (
    <div
      className="flex items-center gap-3 px-4 py-2.5 border-b shrink-0"
      style={{ background: 'var(--surface)', borderColor: 'var(--border)', height: '52px' }}
    >
      <button
        onClick={() => navigate('/')}
        className="p-1.5 rounded-lg hover:opacity-80 transition-opacity"
        style={{ color: 'var(--text-muted)' }}
      >
        <ArrowLeft size={16} />
      </button>

      <div className="w-px h-5" style={{ background: 'var(--border)' }} />

      {/* Agent name */}
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ background: statusColors[agent?.status] || '#64748b' }} />
        <input
          value={agent?.name || ''}
          onChange={async (e) => {
            setAgent({ ...agent, name: e.target.value })
          }}
          className="text-sm font-semibold bg-transparent outline-none border-b border-transparent hover:border-slate-600 text-white"
          style={{ minWidth: '120px', maxWidth: '240px' }}
        />
        {isDirty && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>●</span>}
      </div>

      <div className="flex-1" />

      {/* Validation badge */}
      {validation && (
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono"
          style={{
            background: validation.valid ? '#10b98122' : '#ef444422',
            color: validation.valid ? '#10b981' : '#ef4444',
            border: `1px solid ${validation.valid ? '#10b98144' : '#ef444444'}`,
          }}
        >
          {validation.valid ? <CheckCircle size={12} /> : <AlertCircle size={12} />}
          {validation.valid ? `${validation.node_count}n ${validation.edge_count}e` : `${validation.errors.length} errors`}
        </div>
      )}

      {latestRunId && (
        <div
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono"
          style={{
            background: '#6366f122',
            color: '#a5b4fc',
            border: '1px solid #818cf844',
          }}
        >
          Run #{latestRunId}
        </div>
      )}

      {/* Buttons */}
      <button
        onClick={onSchemaEdit}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80"
        style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
      >
        <Database size={12} /> State Schema
      </button>

      <button
        onClick={handleValidate}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80"
        style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
      >
        <CheckCircle size={12} /> Validate
      </button>

      <button
        onClick={handleExport}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80"
        style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
      >
        <Download size={12} /> Export
      </button>

      <button
        onClick={onRearrangeGraph}
        disabled={!hasEntryNode || !onRearrangeGraph || isRearranging}
        title={hasEntryNode ? 'Rearrange graph from the entry node' : 'Set an entry node to enable graph rearrange'}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80 disabled:opacity-50"
        style={{ background: '#6366f1', border: '1px solid #818cf8', color: '#fff' }}
      >
        <Sparkles size={12} /> {isRearranging ? 'Rearranging...' : 'Rearrange'}
      </button>

      {canUndoLayout && (
        <button
          onClick={onUndoLayout}
          disabled={!onUndoLayout || isRearranging}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80 disabled:opacity-50"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
        >
          <Undo2 size={12} /> Undo
        </button>
      )}

      <button
        onClick={onRun}
        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
        style={{ background: '#6366f1', color: '#fff' }}
      >
        <Play size={12} fill="#fff" /> Run
      </button>
    </div>
  )
}
