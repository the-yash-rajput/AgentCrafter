import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Edit3, Trash2, Copy, Play, Clock, GitBranch, Brain, Upload, X } from 'lucide-react'
import { getAgents, createAgent, deleteAgent, duplicateAgent, importAgent, updateAgent } from '../../api/client'
import toast from 'react-hot-toast'

const statusColors = {
  draft: { bg: '#64748b22', text: '#94a3b8', border: '#64748b44' },
  active: { bg: '#10b98122', text: '#10b981', border: '#10b98144' },
  archived: { bg: '#f59e0b22', text: '#f59e0b', border: '#f59e0b44' },
}

const STATUSES = ['draft', 'active', 'archived']

const AgentCard = ({ agent, onOpen, onEditDetails, onDelete, onDuplicate }) => {
  const s = statusColors[agent.status] || statusColors.draft
  const nodeCount = (agent.nodes || []).length
  const edgeCount = (agent.edges || []).length

  return (
    <div
      className="group rounded-2xl p-5 transition-all duration-200 hover:translate-y-[-2px]"
      style={{
        background: 'var(--surface)',
        border: '1px solid var(--border)',
        cursor: 'pointer',
      }}
      onClick={() => onOpen(agent)}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span
              className="px-2 py-0.5 rounded-full text-xs font-mono"
              style={{ background: s.bg, color: s.text, border: `1px solid ${s.border}` }}
            >
              {agent.status}
            </span>
          </div>
          <h3 className="font-semibold text-white text-base truncate">{agent.name}</h3>
          {agent.description && (
            <p className="text-xs mt-1 line-clamp-2" style={{ color: 'var(--text-muted)' }}>
              {agent.description}
            </p>
          )}
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 mb-4">
        <div className="flex items-center gap-1.5">
          <div className="p-1 rounded" style={{ background: '#7c3aed22' }}>
            <Brain size={10} style={{ color: '#a78bfa' }} />
          </div>
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{nodeCount} nodes</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="p-1 rounded" style={{ background: '#6366f122' }}>
            <GitBranch size={10} style={{ color: '#818cf8' }} />
          </div>
          <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>{edgeCount} edges</span>
        </div>
      </div>

      {/* Date */}
      <div className="flex items-center gap-1 mb-4">
        <Clock size={10} style={{ color: 'var(--text-muted)' }} />
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {new Date(agent.updated_at).toLocaleDateString()}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
        <button
          onClick={() => onEditDetails(agent)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-80"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
        >
          <Edit3 size={11} /> Edit
        </button>
        <button
          onClick={() => onOpen(agent)}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
          style={{ background: '#6366f1', color: '#fff' }}
        >
          <Play size={11} fill="#fff" /> Open
        </button>
        <button
          onClick={() => onDuplicate(agent.id)}
          className="p-1.5 rounded-lg transition-colors hover:opacity-80"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-muted)' }}
        >
          <Copy size={13} />
        </button>
        <button
          onClick={() => onDelete(agent.id)}
          className="p-1.5 rounded-lg transition-colors hover:bg-red-900/20"
          style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: '#ef4444' }}
        >
          <Trash2 size={13} />
        </button>
      </div>
    </div>
  )
}

const CreateModal = ({ onClose, onCreate }) => {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [creating, setCreating] = useState(false)

  const handleCreate = async () => {
    if (!name.trim()) { toast.error('Name required'); return }
    setCreating(true)
    try {
      const agent = await createAgent({ name: name.trim(), description: desc })
      onCreate(agent)
      onClose()
    } catch (e) {
      toast.error('Failed to create agent')
    }
    setCreating(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="w-[480px] rounded-2xl fade-in" style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}>
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-base font-semibold text-white">New Agent</h2>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-mono mb-1.5" style={{ color: 'var(--text-muted)' }}>Agent Name *</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleCreate()}
              placeholder="My AI Workflow"
              autoFocus
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </div>
          <div>
            <label className="block text-xs font-mono mb-1.5" style={{ color: 'var(--text-muted)' }}>Description</label>
            <textarea
              value={desc}
              onChange={e => setDesc(e.target.value)}
              placeholder="What does this agent do?"
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 pb-6">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Cancel</button>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="px-5 py-2 rounded-lg text-sm font-semibold"
            style={{ background: '#6366f1', color: '#fff', opacity: creating ? 0.6 : 1 }}
          >
            {creating ? 'Creating...' : 'Create Agent'}
          </button>
        </div>
      </div>
    </div>
  )
}

const EditDetailsModal = ({ agent, onClose, onSave }) => {
  const [name, setName] = useState(agent.name)
  const [desc, setDesc] = useState(agent.description || '')
  const [status, setStatus] = useState(agent.status)
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    if (!name.trim()) { toast.error('Name required'); return }
    setSaving(true)
    try {
      const updated = await updateAgent(agent.id, {
        name: name.trim(),
        description: desc,
        status,
      })
      onSave(updated)
      onClose()
      toast.success('Agent updated')
    } catch (e) {
      toast.error('Failed to update agent')
    }
    setSaving(false)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div className="w-[480px] rounded-2xl fade-in" style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}>
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-base font-semibold text-white">Edit Agent</h2>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-xs font-mono mb-1.5" style={{ color: 'var(--text-muted)' }}>Agent Name *</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSave()}
              autoFocus
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </div>
          <div>
            <label className="block text-xs font-mono mb-1.5" style={{ color: 'var(--text-muted)' }}>Description</label>
            <textarea
              value={desc}
              onChange={e => setDesc(e.target.value)}
              rows={3}
              className="w-full px-3 py-2.5 rounded-lg text-sm outline-none resize-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </div>
          <div>
            <label className="block text-xs font-mono mb-1.5" style={{ color: 'var(--text-muted)' }}>Status</label>
            <div className="flex gap-2">
              {STATUSES.map(st => {
                const sc = statusColors[st]
                const selected = st === status
                return (
                  <button
                    key={st}
                    onClick={() => setStatus(st)}
                    className="flex-1 py-2 rounded-lg text-xs font-mono transition-all"
                    style={{
                      background: selected ? sc.bg : 'var(--bg)',
                      color: selected ? sc.text : 'var(--text-muted)',
                      border: `1px solid ${selected ? sc.border : 'var(--border2)'}`,
                    }}
                  >
                    {st}
                  </button>
                )
              })}
            </div>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 pb-6">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>Cancel</button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-5 py-2 rounded-lg text-sm font-semibold"
            style={{ background: '#6366f1', color: '#fff', opacity: saving ? 0.6 : 1 }}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

export const Dashboard = () => {
  const navigate = useNavigate()
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [editingAgent, setEditingAgent] = useState(null)

  useEffect(() => {
    loadAgents()
  }, [])

  const loadAgents = async () => {
    try {
      const data = await getAgents()
      setAgents(data)
    } catch (e) {
      toast.error('Failed to load agents')
    }
    setLoading(false)
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this agent?')) return
    try {
      await deleteAgent(id)
      setAgents(prev => prev.filter(a => a.id !== id))
      toast.success('Agent deleted')
    } catch (e) {
      toast.error('Delete failed')
    }
  }

  const handleDuplicate = async (id) => {
    try {
      const copy = await duplicateAgent(id)
      setAgents(prev => [copy, ...prev])
      toast.success('Agent duplicated')
    } catch (e) {
      toast.error('Duplicate failed')
    }
  }

  const handleAgentSaved = (updated) => {
    setAgents(prev => prev.map(a => a.id === updated.id ? { ...a, ...updated } : a))
  }

  const handleOpenAgent = (agent) => {
    if (!agent?.id) return

    const latestVersion = Array.isArray(agent.versions) && agent.versions.length
      ? [...agent.versions].sort((left, right) => (left.version_number || 0) - (right.version_number || 0)).at(-1)
      : null
    const versionNumber = agent.version_number || latestVersion?.version_number

    navigate(versionNumber ? `/agents/${agent.id}/version/${versionNumber}/edit` : `/agents/${agent.id}/edit`)
  }

  const handleImport = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    try {
      const text = await file.text()
      const data = JSON.parse(text)
      const imported = await importAgent(data)
      setAgents(prev => [imported, ...prev])
      toast.success('Agent imported')
    } catch (e) {
      toast.error('Import failed')
    }
    e.target.value = ''
  }

  return (
    <div className="min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <div className="border-b" style={{ borderColor: 'var(--border)', background: 'var(--surface)' }}>
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl flex items-center justify-center"
                 style={{ background: 'linear-gradient(135deg, #6366f1, #22d3ee)', boxShadow: '0 4px 12px rgba(99,102,241,0.4)' }}>
              <GitBranch size={16} color="#fff" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-white font-mono">Agent Crafter</h1>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Visual AI workflow designer</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <label
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer transition-colors hover:opacity-80"
              style={{ background: 'var(--surface2)', border: '1px solid var(--border2)', color: 'var(--text-dim)' }}
            >
              <Upload size={12} /> Import
              <input type="file" accept=".json" className="hidden" onChange={handleImport} />
            </label>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-xs font-semibold transition-all hover:opacity-90"
              style={{ background: '#6366f1', color: '#fff' }}
            >
              <Plus size={12} /> New Agent
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-6 py-8">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : agents.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 text-center">
            <div className="w-16 h-16 rounded-3xl flex items-center justify-center mb-4"
                 style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}>
              <Brain size={28} style={{ color: 'var(--text-muted)' }} />
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">No agents yet</h2>
            <p className="text-sm mb-6" style={{ color: 'var(--text-muted)' }}>
              Create your first workflow in Agent Crafter to get started
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: '#6366f1', color: '#fff' }}
            >
              <Plus size={14} /> Create First Agent
            </button>
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-semibold text-white">Agents</h2>
                <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{agents.length} workflow{agents.length !== 1 ? 's' : ''}</p>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {agents.map(agent => (
                <AgentCard
                  key={agent.id}
                  agent={agent}
                  onOpen={handleOpenAgent}
                  onEditDetails={(a) => setEditingAgent(a)}
                  onDelete={handleDelete}
                  onDuplicate={handleDuplicate}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {showCreate && (
        <CreateModal
          onClose={() => setShowCreate(false)}
          onCreate={(a) => {
            setAgents(prev => [a, ...prev])
            const versionNumber = a.version_number || a.versions?.[a.versions.length - 1]?.version_number
            navigate(versionNumber ? `/agents/${a.id}/version/${versionNumber}/edit` : `/agents/${a.id}/edit`)
          }}
        />
      )}

      {editingAgent && (
        <EditDetailsModal
          agent={editingAgent}
          onClose={() => setEditingAgent(null)}
          onSave={handleAgentSaved}
        />
      )}
    </div>
  )
}
