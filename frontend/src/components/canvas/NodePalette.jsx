import { Brain, Globe, Code2, GitBranch, X } from 'lucide-react'

const PaletteItem = ({ type, icon: Icon, label, description, color, onDragStart }) => (
  <div
    draggable
    onDragStart={(e) => onDragStart(e, type)}
    className="flex items-start gap-3 p-3 rounded-lg cursor-grab active:cursor-grabbing transition-all duration-150 hover:scale-[1.02]"
    style={{
      background: 'var(--surface2)',
      border: `1px solid var(--border2)`,
      userSelect: 'none',
    }}
  >
    <div className="p-1.5 rounded-lg" style={{ background: `${color}22` }}>
      <Icon size={16} style={{ color }} />
    </div>
    <div className="flex-1 min-w-0">
      <p className="text-sm font-semibold text-white">{label}</p>
      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{description}</p>
    </div>
  </div>
)

export const NodePalette = ({ onClose }) => {
  const onDragStart = (event, nodeType) => {
    event.dataTransfer.setData('application/reactflow', nodeType)
    event.dataTransfer.effectAllowed = 'move'
  }

  return (
    <div
      className="w-64 flex flex-col h-full"
      style={{ background: 'var(--surface)', borderRight: '1px solid var(--border)' }}
    >
      <div className="p-4 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-mono font-bold uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
            Node Palette
          </h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-white/5 transition-colors"
            title="Close palette"
          >
            <X size={14} style={{ color: 'var(--text-muted)' }} />
          </button>
        </div>
        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Drag nodes onto the canvas</p>
      </div>

      <div className="p-3 flex-1 overflow-y-auto">
        <p className="text-xs font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
          LLM Nodes
        </p>
        <div className="space-y-2 mb-5">
          <PaletteItem
            type="llm_call"
            icon={Brain}
            label="LLM Call"
            description="Call Azure OpenAI, Anthropic, or other LLMs"
            color="#7c3aed"
            onDragStart={onDragStart}
          />
        </div>

        <p className="text-xs font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
          Functional Nodes
        </p>
        <div className="space-y-2">
          <PaletteItem
            type="python_inline"
            icon={Code2}
            label="Python Function"
            description="Run inline Python code"
            color="#0ea5e9"
            onDragStart={onDragStart}
          />
          <PaletteItem
            type="api_call"
            icon={Globe}
            label="API Call"
            description="HTTP GET/POST to external APIs"
            color="#10b981"
            onDragStart={onDragStart}
          />
          <PaletteItem
            type="data_transform"
            icon={GitBranch}
            label="Data Transform"
            description="Map, filter, or reshape state"
            color="#f59e0b"
            onDragStart={onDragStart}
          />
        </div>
      </div>

      <div className="p-3 border-t" style={{ borderColor: 'var(--border)' }}>
        <div className="rounded-lg p-3" style={{ background: 'var(--surface2)', border: '1px solid var(--border2)' }}>
          <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            💡 <span className="text-slate-300">Tip:</span> Connect nodes by dragging from a node's bottom handle to another's top handle.
          </p>
        </div>
      </div>
    </div>
  )
}
