import { Handle, Position } from 'reactflow'
import { Brain, Code2, Globe, GitBranch, Zap } from 'lucide-react'
import { useGraphStore } from '../../hooks/useGraphStore'

const NodeBase = ({ id, data, type, icon: Icon, color, glowClass, headerLabel }) => {
  const { selectNode, selectedNode, agent } = useGraphStore()
  const isSelected = selectedNode?.id === id
  const isEntry = agent?.entry_node === id
  const isExit = agent?.exit_node === id

  return (
    <div
      onClick={() => selectNode({ id, data, type })}
      className={`relative min-w-[180px] rounded-xl border cursor-pointer transition-all duration-200 ${glowClass} ${
        isSelected ? 'node-selected scale-105' : 'hover:scale-102'
      }`}
      style={{
        background: 'var(--surface2)',
        borderColor: isSelected ? color : 'var(--border2)',
      }}
    >
      <Handle type="target" position={Position.Top} />

      {/* Header */}
      <div
        className="flex items-center gap-2 px-3 py-2 rounded-t-xl"
        style={{ background: `${color}22`, borderBottom: `1px solid ${color}44` }}
      >
        <Icon size={13} style={{ color }} />
        <span className="text-xs font-mono font-semibold uppercase tracking-widest" style={{ color }}>
          {headerLabel || (type === 'llmNode' ? 'LLM Call' : 'Functional')}
        </span>
        {isEntry && (
          <span className="ml-auto text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--success)', color: '#fff', fontSize: '9px' }}>
            ENTRY
          </span>
        )}
        {isExit && (
          <span className="ml-auto text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--warning)', color: '#000', fontSize: '9px' }}>
            EXIT
          </span>
        )}
      </div>

      {/* Body */}
      <div className="px-3 py-2.5">
        <p className="font-semibold text-sm text-white truncate">{data.label || data.name}</p>
        <NodeMeta data={data} type={type} />
      </div>

      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const NodeMeta = ({ data, type }) => {
  const cfg = data.config || {}
  if (type === 'llmNode') {
    return (
      <div className="flex items-center gap-1.5 mt-1">
        <span className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: '#7c3aed33', color: '#a78bfa' }}>
          {cfg.provider || 'azure_openai'}
        </span>
        <span className="text-xs text-slate-400 truncate">{cfg.model || 'ai-agent-4o'}</span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-1.5 mt-1">
      <span className="text-xs px-1.5 py-0.5 rounded font-mono" style={{ background: '#0ea5e933', color: '#38bdf8' }}>
        {cfg.function_type || 'python_inline'}
      </span>
    </div>
  )
}

export const LLMNode = (props) => (
  <NodeBase {...props} type="llmNode" icon={Brain} color="#7c3aed" glowClass="node-llm" headerLabel="LLM Call" />
)

const FUNCTION_VISUALS = {
  python_inline: { icon: Code2, color: '#0ea5e9', label: 'Python Fn' },
  api_call: { icon: Globe, color: '#10b981', label: 'API Call' },
  data_transform: { icon: GitBranch, color: '#f59e0b', label: 'Transform' },
}

export const FunctionalNode = (props) => {
  const fnType = props?.data?.config?.function_type || 'python_inline'
  const visual = FUNCTION_VISUALS[fnType] || { icon: Zap, color: '#0ea5e9', label: 'Functional' }

  return (
    <NodeBase
      {...props}
      type="functionalNode"
      icon={visual.icon}
      color={visual.color}
      glowClass="node-functional"
      headerLabel={visual.label}
    />
  )
}

export const nodeTypes = {
  llmNode: LLMNode,
  functionalNode: FunctionalNode,
}
