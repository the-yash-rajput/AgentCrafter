import { useEffect, useState } from 'react'
import { Brain, Globe, Code2, X, Boxes, RadioTower, Waypoints } from 'lucide-react'
import { getNodeDefinitions } from '../../api/client'

const PaletteItem = ({ definition, icon: Icon, color, onDragStart }) => (
  <div
    draggable
    onDragStart={(e) => onDragStart(e, definition)}
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
      <p className="text-sm font-semibold text-white">{definition.label}</p>
      <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>{definition.description}</p>
    </div>
  </div>
)

export const NodePalette = ({ onClose }) => {
  const [nodeDefinitions, setNodeDefinitions] = useState([])

  useEffect(() => {
    let isActive = true

    const loadNodeDefinitions = async () => {
      try {
        const definitions = await getNodeDefinitions()
        if (!isActive) return
        setNodeDefinitions(definitions.filter(definition => definition.show_in_frontend !== false))
      } catch (_error) {
        if (!isActive) return
        setNodeDefinitions([])
      }
    }

    loadNodeDefinitions()
    return () => { isActive = false }
  }, [])

  const onDragStart = (event, nodeDefinition) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(nodeDefinition))
    event.dataTransfer.effectAllowed = 'move'
  }

  const iconBySubtype = {
    chat: Brain,
    llm_agent: Boxes,
    python_inline: Code2,
    api_call: Globe,
    agent_call: Boxes,
    rabbitmq_message: RadioTower,
    kafka: Waypoints,
    api: Globe,
  }
  const colorBySubtype = {
    chat: '#7c3aed',
    llm_agent: '#7c3aed',
    python_inline: '#0ea5e9',
    api_call: '#10b981',
    agent_call: '#ec4899',
    rabbitmq_message: '#f97316',
    kafka: '#eab308',
    api: '#14b8a6',
  }
  const categoryLabels = {
    llm: 'LLM Nodes',
    functional: 'Functional Nodes',
    communication: 'Communication Nodes',
  }
  const categoryOrder = ['llm', 'functional', 'communication']
  const groupedDefinitions = categoryOrder
    .map(category => ({
      category,
      label: categoryLabels[category] || category,
      definitions: nodeDefinitions.filter(definition => definition.category === category),
    }))
    .filter(group => group.definitions.length > 0)

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
        {groupedDefinitions.map((group, index) => (
          <div key={group.category} className={index === groupedDefinitions.length - 1 ? '' : 'mb-5'}>
            <p className="text-xs font-mono uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
              {group.label}
            </p>
            <div className="space-y-2">
              {group.definitions.map(definition => (
                <PaletteItem
                  key={`${definition.type}:${definition.subtype}`}
                  definition={definition}
                  icon={iconBySubtype[definition.subtype] || Code2}
                  color={colorBySubtype[definition.subtype] || '#0ea5e9'}
                  onDragStart={onDragStart}
                />
              ))}
            </div>
          </div>
        ))}
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
