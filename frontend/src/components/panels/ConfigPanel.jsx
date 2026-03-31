import { useState, useEffect } from 'react'
import { X, Trash2, Brain, Zap, ChevronDown, ChevronRight, Flag, LogOut } from 'lucide-react'
import { useGraphStore } from '../../hooks/useGraphStore'
import { updateNode, deleteNode, updateAgent, updateEdge, getAgents } from '../../api/client'
import toast from 'react-hot-toast'
import Editor from '@monaco-editor/react'

const Section = ({ title, children, defaultOpen = true }) => {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border-b" style={{ borderColor: 'var(--border)' }}>
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-xs font-mono uppercase tracking-widest hover:opacity-80"
        style={{ color: 'var(--text-muted)' }}
      >
        {title}
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  )
}

const Field = ({ label, children }) => (
  <div className="mb-3">
    <label className="block text-xs mb-1 font-mono" style={{ color: 'var(--text-muted)' }}>{label}</label>
    {children}
  </div>
)

const Input = ({ value, onChange, placeholder, type = 'text' }) => (
  <input
    type={type}
    value={value || ''}
    onChange={e => onChange(e.target.value)}
    placeholder={placeholder}
    className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none transition-colors"
    style={{
      background: 'var(--bg)',
      border: '1px solid var(--border2)',
      color: 'var(--text)',
    }}
    onFocus={e => e.target.style.borderColor = 'var(--accent)'}
    onBlur={e => e.target.style.borderColor = 'var(--border2)'}
  />
)

const Select = ({ value, onChange, options }) => (
  <select
    value={value || ''}
    onChange={e => onChange(e.target.value)}
    className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none"
    style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
  >
    {options.map(o => (
      <option key={o.value} value={o.value}>{o.label}</option>
    ))}
  </select>
)

const Slider = ({ label, value, onChange, min = 0, max = 1, step = 0.1 }) => (
  <Field label={`${label}: ${value}`}>
    <input
      type="range" min={min} max={max} step={step} value={value || 0}
      onChange={e => onChange(parseFloat(e.target.value))}
      className="w-full accent-indigo-500"
    />
  </Field>
)

// ─── LLM Node Config ────────────────────────────────────────────────────────────

const LLMNodeConfig = ({ config, onChange }) => {
  const cfg = config || {}
  const set = (key, val) => onChange({ ...cfg, [key]: val })
  const setNested = (section, key, val) => onChange({ ...cfg, [section]: { ...(cfg[section] || {}), [key]: val } })
  const providerDefaults = {
    azure_openai: { model: 'ai-agent-4o', api_key_env_var: 'AZURE_OPENAI_API_KEY' },
    openai: { model: 'ai-agent-4o', api_key_env_var: 'AZURE_OPENAI_API_KEY' },
    anthropic: { model: 'claude-3-haiku-20240307', api_key_env_var: 'ANTHROPIC_API_KEY' },
    ollama: { model: 'llama3.1', api_key_env_var: '' },
  }
  const providerValue = cfg.provider === 'openai' ? 'azure_openai' : (cfg.provider || 'azure_openai')
  const modelLooksAnthropic = (cfg.model || '').toLowerCase().startsWith('claude')
  const handleProviderChange = (provider) => {
    const defaults = providerDefaults[provider] || {}
    const currentApiKeyEnv = (cfg.api_key_env_var || '').trim()
    const currentModel = (cfg.model || '').trim()
    const next = { ...cfg, provider }

    if (
      !currentApiKeyEnv ||
      currentApiKeyEnv === 'OPENAI_API_KEY' ||
      currentApiKeyEnv === 'AZURE_OPENAI_API_KEY' ||
      currentApiKeyEnv === 'ANTHROPIC_API_KEY'
    ) {
      next.api_key_env_var = defaults.api_key_env_var
    }

    if (!currentModel || currentModel === 'ai-agent-4o' || currentModel === 'gpt-4o' || currentModel === 'claude-3-haiku-20240307' || currentModel === 'llama3.1') {
      next.model = defaults.model
    }

    onChange(next)
  }

  return (
    <>
      <Section title="Model Settings">
        <Field label="Provider">
          <Select value={providerValue} onChange={handleProviderChange} options={[
            { value: 'azure_openai', label: 'Azure OpenAI' },
            { value: 'anthropic', label: 'Anthropic' },
            { value: 'ollama', label: 'Ollama (local)' },
          ]} />
        </Field>
        <Field label="Model">
          <Input value={cfg.model} onChange={v => set('model', v)} placeholder="ai-agent-4o, claude-sonnet-4-20250514..." />
          {modelLooksAnthropic && providerValue !== 'anthropic' && (
            <p className="text-xs mt-1" style={{ color: '#f59e0b' }}>
              Claude models require provider "anthropic" and API key env var "ANTHROPIC_API_KEY".
            </p>
          )}
        </Field>
        <Field label="API Key Env Var">
          <Input
            value={cfg.api_key_env_var}
            onChange={v => set('api_key_env_var', v)}
            placeholder={providerValue === 'anthropic' ? 'ANTHROPIC_API_KEY' : 'AZURE_OPENAI_API_KEY'}
          />
        </Field>
        <Slider label="Temperature" value={cfg.temperature ?? 0.7} onChange={v => set('temperature', v)} />
        <Field label="Max Tokens">
          <Input type="number" value={cfg.max_tokens} onChange={v => set('max_tokens', parseInt(v))} placeholder="1000" />
        </Field>
      </Section>

      <Section title="Prompts">
        <Field label="System Prompt">
          <textarea
            value={cfg.system_prompt || ''}
            onChange={e => set('system_prompt', e.target.value)}
            rows={3}
            placeholder="You are a helpful assistant..."
            className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
            style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
          />
        </Field>
        <Field label="User Prompt Template (use {{state.key}})">
          <textarea
            value={cfg.user_prompt_template || ''}
            onChange={e => set('user_prompt_template', e.target.value)}
            rows={4}
            placeholder="Given {{context}}, answer {{question}}"
            className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
            style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
          />
        </Field>
      </Section>

      <Section title="Output">
        <Field label="Output Key (written to state)">
          <Input value={cfg.output_key} onChange={v => set('output_key', v)} placeholder="llm_response" />
        </Field>
        <label className="flex items-center gap-2 text-sm cursor-pointer">
          <input
            type="checkbox"
            checked={cfg.parse_json_response || false}
            onChange={e => set('parse_json_response', e.target.checked)}
            className="accent-indigo-500"
          />
          <span style={{ color: 'var(--text-dim)' }}>Parse JSON response</span>
        </label>
      </Section>
    </>
  )
}

// ─── Functional Node Config ────────────────────────────────────────────────────

const FunctionalNodeConfig = ({ config, onChange, currentAgentId }) => {
  const cfg = config || {}
  const set = (key, val) => onChange({ ...cfg, [key]: val })
  const setNested = (section, key, val) => onChange({ ...cfg, [section]: { ...(cfg[section] || {}), [key]: val } })
  const [availableAgents, setAvailableAgents] = useState([])

  useEffect(() => {
    let isActive = true
    const loadAgents = async () => {
      try {
        const agents = await getAgents()
        if (!isActive) return
        setAvailableAgents(agents.filter(agent => agent.id !== currentAgentId))
      } catch (_error) {
        if (!isActive) return
        setAvailableAgents([])
      }
    }
    loadAgents()
    return () => { isActive = false }
  }, [currentAgentId])

  return (
    <>
      <Section title="Function Type">
        <Field label="Type">
          <Select value={cfg.function_type} onChange={v => set('function_type', v)} options={[
            { value: 'python_inline', label: 'Python Inline' },
            { value: 'api_call', label: 'API Call' },
            { value: 'data_transform', label: 'Data Transform' },
            { value: 'agent_call', label: 'Agent Call' },
          ]} />
        </Field>
      </Section>

      {(cfg.function_type === 'python_inline' || !cfg.function_type) && (
        <Section title="Python Code">
          <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
            Define a <code className="text-indigo-400">run(state)</code> function that returns a dict. Code runs in an isolated task runner process with blocked imports and a restricted helper set.
          </p>
          <div className="rounded-lg overflow-hidden border" style={{ borderColor: 'var(--border2)', height: 200 }}>
            <Editor
              height="200px"
              defaultLanguage="python"
              value={cfg.python_inline?.code || 'def run(state):\n    # Modify state here\n    return state'}
              onChange={v => setNested('python_inline', 'code', v)}
              theme="vs-dark"
              options={{ minimap: { enabled: false }, fontSize: 12, lineNumbers: 'off', scrollBeyondLastLine: false }}
            />
          </div>
          <div className="grid grid-cols-2 gap-3 mt-3">
            <Field label="Timeout (seconds)">
              <Input
                type="number"
                value={cfg.python_inline?.timeout_seconds ?? 5}
                onChange={value => setNested('python_inline', 'timeout_seconds', value === '' ? '' : parseFloat(value))}
                placeholder="5"
              />
            </Field>
            <Field label="Memory Limit (MB)">
              <Input
                type="number"
                value={cfg.python_inline?.max_memory_mb ?? 256}
                onChange={value => setNested('python_inline', 'max_memory_mb', value === '' ? '' : parseInt(value))}
                placeholder="256"
              />
            </Field>
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            Available helpers: <code className="text-indigo-400">json</code>, <code className="text-indigo-400">math</code>, <code className="text-indigo-400">statistics</code>, <code className="text-indigo-400">datetime</code>, <code className="text-indigo-400">timedelta</code>, <code className="text-indigo-400">uuid4</code>, <code className="text-indigo-400">re</code>. If you need print logs, return <code className="text-indigo-400">printed</code> from your function.
          </p>
        </Section>
      )}

      {cfg.function_type === 'api_call' && (
        <Section title="API Configuration">
          <Field label="URL (supports {{state.key}})">
            <Input value={cfg.api_call?.url} onChange={v => setNested('api_call', 'url', v)} placeholder="https://api.example.com/data" />
          </Field>
          <Field label="Method">
            <Select value={cfg.api_call?.method || 'GET'} onChange={v => setNested('api_call', 'method', v)} options={[
              { value: 'GET', label: 'GET' },
              { value: 'POST', label: 'POST' },
              { value: 'PUT', label: 'PUT' },
              { value: 'DELETE', label: 'DELETE' },
            ]} />
          </Field>
          <Field label="Output Key">
            <Input value={cfg.api_call?.output_key} onChange={v => setNested('api_call', 'output_key', v)} placeholder="api_result" />
          </Field>
          <Field label="Body Template (JSON)">
            <textarea
              value={cfg.api_call?.body_template || ''}
              onChange={e => setNested('api_call', 'body_template', e.target.value)}
              rows={3}
              placeholder='{"query": "{{question}}"}'
              className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </Field>
        </Section>
      )}

      {cfg.function_type === 'data_transform' && (
        <Section title="Transform Operations">
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Configure transform operations as JSON:
          </p>
          <div className="rounded-lg overflow-hidden border mt-2" style={{ borderColor: 'var(--border2)', height: 180 }}>
            <Editor
              height="180px"
              defaultLanguage="json"
              value={JSON.stringify(cfg.data_transform?.operations || [], null, 2)}
              onChange={v => { try { setNested('data_transform', 'operations', JSON.parse(v)) } catch(e) {} }}
              theme="vs-dark"
              options={{ minimap: { enabled: false }, fontSize: 12, lineNumbers: 'off' }}
            />
          </div>
        </Section>
      )}

      {cfg.function_type === 'agent_call' && (
        <Section title="Agent Handoff">
          <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
            Use this as a terminal handoff to another agent. The child agent runs immediately and can return merged state.
          </p>
          <Field label="Target Agent">
            <Select
              value={String(cfg.agent_call?.target_agent_id || '')}
              onChange={(value) => {
                const selectedAgent = availableAgents.find(agent => String(agent.id) === value)
                set('agent_call', {
                  ...(cfg.agent_call || {}),
                  target_agent_id: value,
                  target_agent_name: selectedAgent?.name || '',
                })
              }}
              options={[
                { value: '', label: availableAgents.length ? 'Select an agent' : 'No other agents available' },
                ...availableAgents.map(agent => ({
                  value: String(agent.id),
                  label: `${agent.name} (#${agent.id})`,
                })),
              ]}
            />
          </Field>
          <Field label="Input Mode">
            <Select
              value={cfg.agent_call?.input_mode || 'entire_state'}
              onChange={value => setNested('agent_call', 'input_mode', value)}
              options={[
                { value: 'entire_state', label: 'Entire State' },
                { value: 'state_key', label: 'Single State Key' },
                { value: 'template', label: 'JSON Template' },
              ]}
            />
          </Field>
          {cfg.agent_call?.input_mode === 'state_key' && (
            <Field label="Input Key">
              <Input
                value={cfg.agent_call?.input_key}
                onChange={value => setNested('agent_call', 'input_key', value)}
                placeholder="final_payload"
              />
            </Field>
          )}
          {cfg.agent_call?.input_mode === 'template' && (
            <Field label="Input Template (JSON)">
              <textarea
                value={cfg.agent_call?.input_template || ''}
                onChange={e => setNested('agent_call', 'input_template', e.target.value)}
                rows={5}
                placeholder='{"input": "{{input}}", "context": {{context | tojson}}}'
                className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
                style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
              />
            </Field>
          )}
          <Field label="Output Mode">
            <Select
              value={cfg.agent_call?.output_mode || 'merge_state'}
              onChange={value => setNested('agent_call', 'output_mode', value)}
              options={[
                { value: 'merge_state', label: 'Merge Child Output' },
                { value: 'write_to_key', label: 'Write Child Output To Key' },
              ]}
            />
          </Field>
          {cfg.agent_call?.output_mode === 'write_to_key' && (
            <Field label="Output Key">
              <Input
                value={cfg.agent_call?.output_key}
                onChange={value => setNested('agent_call', 'output_key', value)}
                placeholder="agent_result"
              />
            </Field>
          )}
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              checked={cfg.agent_call?.include_run_metadata || false}
              onChange={e => setNested('agent_call', 'include_run_metadata', e.target.checked)}
              className="accent-indigo-500"
            />
            <span style={{ color: 'var(--text-dim)' }}>Attach child run metadata</span>
          </label>
        </Section>
      )}
    </>
  )
}

// ─── Edge Config Panel ─────────────────────────────────────────────────────────

const EdgeConfigPanel = ({ edge, onClose }) => {
  const { nodes, updateEdgeData } = useGraphStore()
  const [config, setConfig] = useState(edge.data?.condition_config || {})
  const [label, setLabel] = useState(edge.data?.label || '')
  const [edgeType, setEdgeType] = useState(edge.data?.edge_type || 'direct')
  const [saving, setSaving] = useState(false)
  const sourceName = nodes.find(n => n.id === String(edge.source))?.data?.name || edge.source
  const targetName = nodes.find(n => n.id === String(edge.target))?.data?.name || edge.target

  useEffect(() => {
    setConfig(edge.data?.condition_config || {})
    setLabel(edge.data?.label || '')
    setEdgeType(edge.data?.edge_type || 'direct')
  }, [edge.id, edge.data])

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateEdge(edge.id, { edge_type: edgeType, condition_config: config, label })
      updateEdgeData(edge.id, { edge_type: edgeType, condition_config: config, label })
      toast.success('Edge updated')
    } catch (e) {
      toast.error('Failed to update edge')
    }
    setSaving(false)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div>
          <p className="text-xs font-mono uppercase tracking-widest" style={{ color: '#f59e0b' }}>Edge Config</p>
          <p className="text-sm font-semibold text-white mt-0.5">{sourceName} → {targetName}</p>
        </div>
        <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
      </div>

      <div className="flex-1 overflow-y-auto">
        <Section title="Edge Type">
          <Field label="Type">
            <Select value={edgeType} onChange={setEdgeType} options={[
              { value: 'direct', label: 'Direct' },
              { value: 'conditional', label: 'Conditional' },
            ]} />
          </Field>
          <Field label="Label">
            <Input value={label} onChange={setLabel} placeholder="Edge label" />
          </Field>
        </Section>

        {edgeType === 'conditional' && (
          <Section title="Condition">
            <Field label="Condition Type">
              <Select
                value={config.condition_type || 'state_key_equals'}
                onChange={v => setConfig({ ...config, condition_type: v })}
                options={[
                  { value: 'state_key_equals', label: 'State Key Equals' },
                  { value: 'python_expression', label: 'Python Expression' },
                  { value: 'llm_router', label: 'LLM Router' },
                ]}
              />
            </Field>

            {config.condition_type === 'state_key_equals' && (
              <>
                <Field label="State Key">
                  <Input
                    value={config.state_key_equals?.key}
                    onChange={v => setConfig({ ...config, state_key_equals: { ...config.state_key_equals, key: v } })}
                    placeholder="decision"
                  />
                </Field>
                <Field label="Expected Value">
                  <Input
                    value={config.state_key_equals?.value}
                    onChange={v => setConfig({ ...config, state_key_equals: { ...config.state_key_equals, value: v } })}
                    placeholder="approve"
                  />
                </Field>
              </>
            )}

            {config.condition_type === 'python_expression' && (
              <Field label="Expression">
                <Input
                  value={config.python_expression?.expression}
                  onChange={v => setConfig({ ...config, python_expression: { expression: v } })}
                  placeholder="state['score'] > 0.8"
                />
              </Field>
            )}

            {config.condition_type === 'llm_router' && (
              <Field label="Routing Key">
                <Input
                  value={config.llm_router?.routing_key}
                  onChange={v => setConfig({ ...config, llm_router: { ...config.llm_router, routing_key: v } })}
                  placeholder="next_step"
                />
              </Field>
            )}
          </Section>
        )}
      </div>

      <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2 rounded-lg text-sm font-semibold transition-opacity"
          style={{ background: '#f59e0b', color: '#000', opacity: saving ? 0.6 : 1 }}
        >
          {saving ? 'Saving...' : 'Save Edge'}
        </button>
      </div>
    </div>
  )
}

// ─── Main Config Panel ─────────────────────────────────────────────────────────

export const ConfigPanel = ({ onClosePanel, panelWidth = 320 }) => {
  const { selectedNode, selectedEdge, clearSelection, agent, edges, updateNodeData, removeNode, setAgent } = useGraphStore()
  const [config, setConfig] = useState({})
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (selectedNode) {
      setConfig(selectedNode.data?.config || {})
      setName(selectedNode.data?.name || selectedNode.id)
    }
  }, [selectedNode])

  if (!selectedNode && !selectedEdge) {
    return (
      <div
        className="flex flex-col h-full"
        style={{ width: `${panelWidth}px`, background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
      >
        <div className="flex items-center justify-end px-3 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
          <button
            onClick={onClosePanel}
            className="p-1.5 rounded hover:bg-white/5 transition-colors"
            title="Close panel"
          >
            <X size={14} style={{ color: 'var(--text-muted)' }} />
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center p-6">
          <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-3"
               style={{ background: 'var(--surface2)', border: '1px solid var(--border2)' }}>
            <Zap size={20} style={{ color: 'var(--text-muted)' }} />
          </div>
          <p className="text-sm font-semibold text-white">No selection</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Click a node or edge to configure it</p>
          </div>
        </div>
      </div>
    )
  }

  if (selectedEdge) {
    return (
      <div
        className="flex flex-col h-full"
        style={{ width: `${panelWidth}px`, background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
      >
        <EdgeConfigPanel edge={selectedEdge} onClose={clearSelection} />
      </div>
    )
  }

  const isLLM = selectedNode.type === 'llmNode'
  const nodeId = selectedNode.id
  const nodeName = selectedNode.data?.name || selectedNode.id
  const exitNodes = agent?.exit_nodes || []
  const isExitNode = exitNodes.includes(nodeName)
  const hasOutgoingEdges = edges.some(edge => edge.source === nodeId)

  const handleSave = async () => {
    setSaving(true)
    try {
      const nodeData = selectedNode.data
      if (nodeData.id) {
        await updateNode(nodeData.id, { name, config })
        updateNodeData(nodeId, { name, config, label: name })
        if (name !== nodeName && agent) {
          const nextExitNodes = exitNodes.map(exitName => exitName === nodeName ? name : exitName)
          setAgent({
            ...agent,
            entry_node: agent.entry_node === nodeName ? name : agent.entry_node,
            exit_nodes: nextExitNodes,
            exit_node: nextExitNodes[0] || null,
          })
        }
        toast.success('Node saved')
      }
    } catch (e) {
      toast.error('Failed to save: ' + (e.response?.data?.detail || e.message))
    }
    setSaving(false)
  }

  const handleDelete = async () => {
    try {
      if (selectedNode.data.id) await deleteNode(selectedNode.data.id)
      removeNode(nodeId)
      clearSelection()
      toast.success('Node removed')
    } catch (e) {
      toast.error('Failed to delete node')
    }
  }

  const handleSetEntry = async () => {
    try {
      const updated = await updateAgent(agent.id, { entry_node: nodeName })
      setAgent(updated)
      toast.success(`${nodeName} set as entry node`)
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed') }
  }

  const handleSetExit = async () => {
    try {
      const nextExitNodes = isExitNode
        ? exitNodes.filter(exitName => exitName !== nodeName)
        : [...exitNodes, nodeName]
      const updated = await updateAgent(agent.id, { exit_nodes: nextExitNodes })
      setAgent(updated)
      toast.success(isExitNode ? `${nodeName} removed from exit nodes` : `${nodeName} added to exit nodes`)
    } catch (e) { toast.error(e.response?.data?.detail || 'Failed') }
  }

  return (
    <div
      className="flex flex-col h-full"
      style={{ width: `${panelWidth}px`, background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg" style={{ background: isLLM ? '#7c3aed22' : '#0ea5e922' }}>
            {isLLM ? <Brain size={14} style={{ color: '#7c3aed' }} /> : <Zap size={14} style={{ color: '#0ea5e9' }} />}
          </div>
          <div>
            <p className="text-xs font-mono uppercase tracking-widest" style={{ color: isLLM ? '#a78bfa' : '#38bdf8' }}>
              {isLLM ? 'LLM Node' : 'Functional Node'}
            </p>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              className="text-sm font-semibold bg-transparent outline-none border-b border-transparent hover:border-slate-600 text-white"
              style={{ maxWidth: '160px' }}
            />
          </div>
        </div>
        <div className="flex items-center gap-1">
          <button onClick={handleDelete} className="p-1.5 rounded hover:bg-red-900/30 transition-colors">
            <Trash2 size={14} style={{ color: '#ef4444' }} />
          </button>
          <button onClick={clearSelection} className="p-1.5 rounded hover:bg-white/5 transition-colors">
            <X size={14} style={{ color: 'var(--text-muted)' }} />
          </button>
        </div>
      </div>

      {/* Quick actions */}
      <div className="flex gap-2 px-4 py-2 border-b" style={{ borderColor: 'var(--border)' }}>
        <button
          onClick={handleSetEntry}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:opacity-80"
          style={{
            background: agent?.entry_node === nodeName ? '#10b98133' : 'var(--surface2)',
            color: agent?.entry_node === nodeName ? '#10b981' : 'var(--text-muted)',
            border: '1px solid',
            borderColor: agent?.entry_node === nodeName ? '#10b981' : 'var(--border2)',
          }}
        >
          <Flag size={10} /> Entry
        </button>
        <button
          onClick={handleSetExit}
          disabled={hasOutgoingEdges && !isExitNode}
          title={hasOutgoingEdges && !isExitNode ? 'Only leaf nodes can be marked as exits' : 'Toggle exit node'}
          className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:opacity-80 disabled:opacity-50"
          style={{
            background: isExitNode ? '#f59e0b33' : 'var(--surface2)',
            color: isExitNode ? '#f59e0b' : 'var(--text-muted)',
            border: '1px solid',
            borderColor: isExitNode ? '#f59e0b' : 'var(--border2)',
          }}
        >
          <LogOut size={10} /> Exit
        </button>
      </div>

      {/* Config form */}
      <div className="flex-1 overflow-y-auto">
        {isLLM
          ? <LLMNodeConfig config={config} onChange={setConfig} />
          : <FunctionalNodeConfig config={config} onChange={setConfig} currentAgentId={agent?.id} />
        }
      </div>

      {/* Save */}
      <div className="p-4 border-t" style={{ borderColor: 'var(--border)' }}>
        <button
          onClick={handleSave}
          disabled={saving}
          className="w-full py-2 rounded-lg text-sm font-semibold transition-all"
          style={{
            background: 'var(--accent)',
            color: '#fff',
            opacity: saving ? 0.6 : 1,
          }}
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  )
}
