import { useState } from 'react'
import { Plus, Trash2, X } from 'lucide-react'
import { updateAgent } from '../../api/client'
import toast from 'react-hot-toast'

const TYPE_OPTIONS = ['str', 'int', 'float', 'bool', 'list', 'dict', 'Any']

export const StateSchemaEditor = ({ agent, onClose, onUpdate }) => {
  const schema = agent?.state_schema || {}
  const [fields, setFields] = useState(
    Object.entries(schema).map(([key, value]) => ({
      key,
      type: value.type || 'str',
      default: value.default ?? '',
      description: value.description || '',
    }))
  )

  const addField = () => {
    setFields([...fields, { key: '', type: 'str', default: '', description: '' }])
  }

  const removeField = (i) => setFields(fields.filter((_, idx) => idx !== i))

  const updateField = (i, key, val) => {
    setFields(fields.map((f, idx) => idx === i ? { ...f, [key]: val } : f))
  }

  const handleSave = async () => {
    const schema = {}
    for (const f of fields) {
      if (f.key) {
        schema[f.key] = { type: f.type, default: f.default, description: f.description }
      }
    }
    try {
      await updateAgent(agent.id, { state_schema: schema })
      onUpdate({ ...agent, state_schema: schema })
      toast.success('State schema saved')
      onClose()
    } catch (e) {
      toast.error('Failed to save schema')
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center" style={{ background: 'rgba(0,0,0,0.7)' }}>
      <div
        className="w-[680px] max-h-[80vh] flex flex-col rounded-2xl"
        style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b" style={{ borderColor: 'var(--border)' }}>
          <div>
            <h2 className="text-base font-semibold text-white">State Schema</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Define keys available in agent state — shared across all nodes
            </p>
          </div>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6">
          {/* Header row */}
          <div className="grid grid-cols-12 gap-2 mb-2 text-xs font-mono uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            <div className="col-span-3">Key Name</div>
            <div className="col-span-2">Type</div>
            <div className="col-span-3">Default</div>
            <div className="col-span-3">Description</div>
            <div className="col-span-1"></div>
          </div>

          <div className="space-y-2">
            {fields.map((field, i) => (
              <div key={i} className="grid grid-cols-12 gap-2 items-center">
                <input
                  value={field.key}
                  onChange={e => updateField(i, 'key', e.target.value)}
                  placeholder="key_name"
                  className="col-span-3 px-2 py-1.5 rounded text-sm font-mono outline-none"
                  style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
                />
                <select
                  value={field.type}
                  onChange={e => updateField(i, 'type', e.target.value)}
                  className="col-span-2 px-2 py-1.5 rounded text-sm font-mono outline-none"
                  style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
                >
                  {TYPE_OPTIONS.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
                <input
                  value={field.default}
                  onChange={e => updateField(i, 'default', e.target.value)}
                  placeholder="default value"
                  className="col-span-3 px-2 py-1.5 rounded text-sm font-mono outline-none"
                  style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
                />
                <input
                  value={field.description}
                  onChange={e => updateField(i, 'description', e.target.value)}
                  placeholder="optional..."
                  className="col-span-3 px-2 py-1.5 rounded text-sm outline-none"
                  style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
                />
                <button onClick={() => removeField(i)} className="col-span-1 flex justify-center">
                  <Trash2 size={14} style={{ color: '#ef4444' }} />
                </button>
              </div>
            ))}
          </div>

          <button
            onClick={addField}
            className="flex items-center gap-2 mt-4 px-3 py-2 rounded-lg text-sm transition-colors"
            style={{ background: 'var(--surface2)', border: '1px dashed var(--border2)', color: 'var(--text-muted)' }}
          >
            <Plus size={14} /> Add State Key
          </button>
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t" style={{ borderColor: 'var(--border)' }}>
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm" style={{ color: 'var(--text-muted)' }}>
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 rounded-lg text-sm font-semibold"
            style={{ background: 'var(--accent)', color: '#fff' }}
          >
            Save Schema
          </button>
        </div>
      </div>
    </div>
  )
}
