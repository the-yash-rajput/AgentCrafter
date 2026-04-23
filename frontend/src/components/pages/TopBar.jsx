import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeft, Play, Database, Download, CheckCircle, AlertCircle, ChevronDown, Sparkles, Undo2, GitBranch } from 'lucide-react'
import { validateAgent, exportAgent, getVersions, forkVersion, createSession } from '../../api/client'
import toast from 'react-hot-toast'

export const TopBar = ({
  agent,
  versionId,
  isDirty,
  onSchemaEdit,
  onRearrangeGraph,
  onUndoLayout,
  canUndoLayout = false,
  isRearranging = false,
}) => {
  const navigate = useNavigate()
  const [validation, setValidation] = useState(null)
  const [versions, setVersions] = useState([])
  const [showVersionMenu, setShowVersionMenu] = useState(false)
  const [forking, setForking] = useState(false)
  const [launching, setLaunching] = useState(false)
  const [showForkConfirm, setShowForkConfirm] = useState(false)
  const versionMenuRef = useRef(null)
  const hasEntryNode = Boolean(agent?.entry_node)

  useEffect(() => {
    if (!agent?.id) return
    getVersions(agent.id).then(setVersions).catch(() => {})
  }, [agent?.id])

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (versionMenuRef.current && !versionMenuRef.current.contains(e.target)) {
        setShowVersionMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleValidate = async () => {
    try {
      const result = await validateAgent(agent.id)
      setValidation(result)
      if (result.valid) toast.success(`Valid graph — ${result.node_count} nodes, ${result.edge_count} edges`)
      else toast.error(`${result.errors.length} validation error(s)`)
    } catch {
      toast.error('Validation failed')
    }
  }

  const handleExport = async () => {
    try {
      const data = await exportAgent(agent.id, versionId)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${agent.name}.json`
      a.click()
      toast.success('Exported')
    } catch {
      toast.error('Export failed')
    }
  }

  const handleFork = () => {
    if (!agent?.id || !versionId || forking) return
    setShowForkConfirm(true)
  }

  const confirmFork = async () => {
    setShowForkConfirm(false)
    setForking(true)
    try {
      const newVersion = await forkVersion(agent.id, versionId)
      toast.success(`Created v${newVersion.version_number}`)
      window.open(`/agents/${agent.id}/version/${newVersion.id}/edit`, '_blank')
    } catch {
      toast.error('Fork failed')
    }
    setForking(false)
  }

  const handleRun = async () => {
    if (!agent?.id || !versionId || launching) return
    setLaunching(true)
    try {
      const session = await createSession(agent.id, versionId)
      window.open(`/agents/${agent.id}/version/${versionId}/session/${session.id}`, '_blank')
    } catch {
      toast.error('Failed to create session')
    }
    setLaunching(false)
  }

  const currentVersion = versions.find(v => v.id === Number(versionId))
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
        <div
          className="text-sm font-semibold text-white truncate"
          style={{ minWidth: '120px', maxWidth: '240px' }}
          title={agent?.name || `Agent ${agent?.id ?? ''}`.trim()}
        >
          {agent?.name || `Agent ${agent?.id ?? ''}`.trim()}
        </div>
        {isDirty && <span className="text-xs" style={{ color: 'var(--text-muted)' }}>●</span>}
      </div>

      {/* Version dropdown */}
      {versions.length > 0 && (
        <div className="relative" ref={versionMenuRef}>
          <button
            onClick={() => setShowVersionMenu(v => !v)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-mono transition-colors hover:opacity-80"
            style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
          >
            {currentVersion ? `v${currentVersion.version_number}` : 'v?'}
            <ChevronDown size={10} />
          </button>
          {showVersionMenu && (
            <div
              className="absolute top-full left-0 mt-1 py-1 rounded-lg z-50 min-w-[120px]"
              style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}
            >
              {versions.map(v => (
                <button
                  key={v.id}
                  onClick={() => {
                    setShowVersionMenu(false)
                    window.open(`/agents/${agent.id}/version/${v.id}/edit`, '_blank')
                  }}
                  className="w-full text-left px-3 py-1.5 text-xs hover:opacity-80"
                  style={{
                    color: v.id === Number(versionId) ? 'var(--accent)' : 'var(--text-dim)',
                    fontWeight: v.id === Number(versionId) ? 600 : 400,
                  }}
                >
                  v{v.version_number}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

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
        onClick={handleFork}
        disabled={forking || !versionId}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80 disabled:opacity-50"
        style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
      >
        <GitBranch size={12} /> {forking ? 'Forking...' : 'Fork'}
      </button>

      <button
        onClick={handleRun}
        disabled={launching}
        className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90 disabled:opacity-60"
        style={{ background: '#6366f1', color: '#fff' }}
      >
        <Play size={12} fill="#fff" /> {launching ? 'Starting...' : 'Run'}
      </button>

      {showForkConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.6)' }}
          onClick={() => setShowForkConfirm(false)}
        >
          <div
            className="rounded-xl p-6 flex flex-col gap-4 min-w-[320px] shadow-xl"
            style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center gap-2">
              <GitBranch size={18} style={{ color: 'var(--accent)' }} />
              <span className="text-sm font-semibold" style={{ color: 'var(--text)' }}>Fork Version</span>
            </div>
            <p className="text-sm" style={{ color: 'var(--text-dim)' }}>
              Are you sure you want to fork{' '}
              <span className="font-mono font-semibold" style={{ color: 'var(--text)' }}>
                v{currentVersion?.version_number ?? "NA"}
              </span>
              ? <>
                <br />
                A new version will be created from this one.
              </>
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowForkConfirm(false)}
                className="px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80"
                style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
              >
                Cancel
              </button>
              <button
                onClick={confirmFork}
                className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors hover:opacity-80"
                style={{ background: '#6366f1', color: '#fff' }}
              >
                <GitBranch size={12} /> Fork
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
