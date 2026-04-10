import { useState, useEffect } from 'react'
import { X, Trash2, Brain, Zap, ChevronDown, ChevronRight, Flag, LogOut, RadioTower, Copy } from 'lucide-react'
import { useGraphStore } from '../../hooks/useGraphStore'
import { updateNode, deleteNode, updateAgent, updateEdge, deleteEdge, getAgents, getLangfusePrompts, getNodeDefinitions } from '../../api/client'
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

const Select = ({ value, onChange, options, disabled = false }) => (
  <select
    value={value || ''}
    onChange={e => onChange(e.target.value)}
    disabled={disabled}
    className={`w-full px-3 py-2 rounded-lg text-sm font-mono outline-none ${disabled ? 'cursor-not-allowed opacity-70' : ''}`}
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

const STRUCTURED_OUTPUT_SCHEMA_PLACEHOLDER = `{
  "title": "AgentResponse",
  "type": "object",
  "properties": {
    "summary": { "type": "string" },
    "confidence": { "type": "number" }
  },
  "required": ["summary", "confidence"],
  "additionalProperties": false
}`

const normalizeStructuredOutputSchemaText = (value) => {
  if (typeof value === 'string') {
    return value
  }
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value, null, 2)
    } catch (_error) {
      return ''
    }
  }
  return value == null ? '' : String(value)
}

const parseStructuredOutputSchema = (value) => {
  const schemaText = normalizeStructuredOutputSchemaText(value).trim()
  if (!schemaText) {
    return null
  }

  let parsed
  try {
    parsed = JSON.parse(schemaText)
  } catch (error) {
    throw new Error(`Structured output schema must be valid JSON. ${error.message}`)
  }

  if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') {
    throw new Error('Structured output schema must be a JSON object schema.')
  }

  return parsed
}

const normalizeNodeConfigForSave = (selectedNode, config) => {
  const normalizedConfig = { ...(config || {}) }
  delete normalizedConfig.llm_runtime

  if (selectedNode?.type !== 'llmNode') {
    return normalizedConfig
  }

  if (!normalizedConfig.structured_output_enabled) {
    normalizedConfig.structured_output_schema = ''
    return normalizedConfig
  }

  const parsedSchema = parseStructuredOutputSchema(normalizedConfig.structured_output_schema)
  if (!parsedSchema) {
    throw new Error('Structured output is enabled, but no response schema was provided.')
  }

  normalizedConfig.structured_output_schema = JSON.stringify(parsedSchema, null, 2)
  return normalizedConfig
}

// ─── LLM Node Config ────────────────────────────────────────────────────────────

const LLMNodeConfig = ({ config, onChange }) => {
  const cfg = config || {}
  const set = (key, val) => onChange({ ...cfg, [key]: val })
  const [llmDefinitions, setLlmDefinitions] = useState([])
  const [langfusePrompts, setLangfusePrompts] = useState([])
  const [langfusePromptsLoading, setLangfusePromptsLoading] = useState(false)
  const [langfusePromptSource, setLangfusePromptSource] = useState('')
  const [langfusePromptError, setLangfusePromptError] = useState('')
  const providerDefaults = {
    azure_openai: { model: 'ai-agent-4o', api_key_env_var: 'AZURE_OPENAI_API_KEY' },
    openai: { model: 'ai-agent-4o', api_key_env_var: 'AZURE_OPENAI_API_KEY' },
    anthropic: { model: 'claude-3-haiku-20240307', api_key_env_var: 'ANTHROPIC_API_KEY' },
    ollama: { model: 'llama3.1', api_key_env_var: '' },
  }
  const providerValue = cfg.provider === 'openai' ? 'azure_openai' : (cfg.provider || 'azure_openai')
  const modelLooksAnthropic = (cfg.model || '').toLowerCase().startsWith('claude')
  const selectedLangfusePrompt = (cfg.langfuse_prompt_name || '').trim()
  const llmType = cfg.llm_type || 'chat'
  const structuredOutputSchemaText = normalizeStructuredOutputSchemaText(cfg.structured_output_schema)
  let structuredOutputValidationError = ''
  if (cfg.structured_output_enabled) {
    try {
      if (!structuredOutputSchemaText.trim()) {
        structuredOutputValidationError = 'Provide a JSON schema to enable structured output.'
      } else {
        parseStructuredOutputSchema(structuredOutputSchemaText)
      }
    } catch (error) {
      structuredOutputValidationError = error.message
    }
  }
  const langfusePromptOptions = [
    {
      value: '',
      label: langfusePromptsLoading
        ? 'Loading prompts...'
        : langfusePrompts.length
          ? 'Select a prompt'
          : 'No prompts available',
    },
    ...langfusePrompts.map(promptName => ({
      value: promptName,
      label: promptName,
    })),
  ]
  if (selectedLangfusePrompt && !langfusePrompts.includes(selectedLangfusePrompt)) {
    langfusePromptOptions.push({
      value: selectedLangfusePrompt,
      label: `${selectedLangfusePrompt} (current)`,
    })
  }
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

  useEffect(() => {
    let isActive = true

    const loadNodeDefinitions = async () => {
      try {
        const definitions = await getNodeDefinitions()
        if (!isActive) return
        setLlmDefinitions(
          definitions.filter(definition => definition.type === 'llm_call' && definition.show_in_frontend !== false)
        )
      } catch (_error) {
        if (!isActive) return
        setLlmDefinitions([])
      }
    }

    loadNodeDefinitions()
    return () => { isActive = false }
  }, [])

  useEffect(() => {
    let isActive = true

    const loadLangfusePrompts = async () => {
      if (!cfg.use_langfuse_prompt) {
        if (!isActive) return
        setLangfusePrompts([])
        setLangfusePromptsLoading(false)
        setLangfusePromptSource('')
        setLangfusePromptError('')
        return
      }

      setLangfusePromptsLoading(true)
      setLangfusePromptError('')
      try {
        const response = await getLangfusePrompts()
        if (!isActive) return
        setLangfusePrompts(Array.isArray(response.prompts) ? response.prompts : [])
        setLangfusePromptSource(response.source || '')
        setLangfusePromptError(response.error || '')
      } catch (_error) {
        if (!isActive) return
        setLangfusePrompts([])
        setLangfusePromptSource('')
        setLangfusePromptError('Failed to load prompt list.')
      } finally {
        if (isActive) {
          setLangfusePromptsLoading(false)
        }
      }
    }

    loadLangfusePrompts()
    return () => { isActive = false }
  }, [cfg.use_langfuse_prompt])

  return (
    <>
      <Section title="LLM Type">
        <Field label="Type">
          <Select
            value={llmType}
            onChange={v => set('llm_type', v)}
            disabled
            options={llmDefinitions.map(definition => ({
              value: definition.subtype,
              label: definition.label,
            }))}
          />
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            {llmType === 'llm_agent'
              ? 'LLM Agent uses LangChain create_agent with middleware and richer Langfuse traces.'
              : 'LLM Call invokes the model directly without the agent loop.'} Type is locked after node creation.
          </p>
        </Field>
      </Section>
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
        <label className="flex items-center gap-2 text-sm cursor-pointer mb-3">
          <input
            type="checkbox"
            checked={cfg.use_langfuse_prompt || false}
            onChange={e => set('use_langfuse_prompt', e.target.checked)}
            className="accent-indigo-500"
          />
          <span style={{ color: 'var(--text-dim)' }}>Fetch system prompt from Langfuse</span>
        </label>
        {cfg.use_langfuse_prompt && (
          <Field label="Langfuse Prompt">
            <Select
              value={cfg.langfuse_prompt_name || ''}
              onChange={value => set('langfuse_prompt_name', value)}
              options={langfusePromptOptions}
            />
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Backend resolves labels from `PROFILE_ENV` and `ENV_NAMESPACE`, then falls back to the inline system prompt below.
            </p>
            {!!langfusePromptSource && (
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                Source: {langfusePromptSource}
              </p>
            )}
            {!!langfusePromptError && (
              <p className="text-xs mt-1" style={{ color: '#f59e0b' }}>
                {langfusePromptError}
              </p>
            )}
            {!langfusePromptsLoading && langfusePrompts.length === 0 && (
              <div className="mt-2">
                <Input
                  value={cfg.langfuse_prompt_name || ''}
                  onChange={v => set('langfuse_prompt_name', v)}
                  placeholder="Manual prompt name fallback"
                />
              </div>
            )}
          </Field>
        )}
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

      {llmType === 'llm_agent' && (
        <Section title="Structured Output">
          <label className="flex items-center gap-2 text-sm cursor-pointer mb-3">
            <input
              type="checkbox"
              checked={cfg.structured_output_enabled || false}
              onChange={e => set('structured_output_enabled', e.target.checked)}
              className="accent-indigo-500"
            />
            <span style={{ color: 'var(--text-dim)' }}>Enforce a custom response structure</span>
          </label>

          {cfg.structured_output_enabled && (
            <>
              <p className="text-xs mb-2" style={{ color: 'var(--text-muted)' }}>
                Provide a JSON Schema object. The backend passes it to <code className="text-indigo-400">create_agent(response_format=...)</code> and stores the structured response under the output key.
              </p>
              <Field label="Response Schema (JSON Schema)">
                <textarea
                  value={structuredOutputSchemaText}
                  onChange={e => set('structured_output_schema', e.target.value)}
                  rows={12}
                  placeholder={STRUCTURED_OUTPUT_SCHEMA_PLACEHOLDER}
                  className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-y"
                  style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
                />
              </Field>
              {structuredOutputValidationError ? (
                <p className="text-xs mt-1" style={{ color: '#f59e0b' }}>
                  {structuredOutputValidationError}
                </p>
              ) : (
                <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                  Use <code className="text-indigo-400">additionalProperties: false</code> if you need strict object shapes.
                </p>
              )}
            </>
          )}
        </Section>
      )}
    </>
  )
}

// ─── Functional Node Config ────────────────────────────────────────────────────

const FunctionalNodeConfig = ({ config, onChange, currentAgentId }) => {
  const cfg = config || {}
  const set = (key, val) => onChange({ ...cfg, [key]: val })
  const setNested = (section, key, val) => onChange({ ...cfg, [section]: { ...(cfg[section] || {}), [key]: val } })
  const [availableAgents, setAvailableAgents] = useState([])
  const [functionDefinitions, setFunctionDefinitions] = useState([])

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

  useEffect(() => {
    let isActive = true

    const loadNodeDefinitions = async () => {
      try {
        const definitions = await getNodeDefinitions()
        if (!isActive) return
        setFunctionDefinitions(
          definitions.filter(definition => definition.type === 'functional' && definition.show_in_frontend !== false)
        )
      } catch (_error) {
        if (!isActive) return
        setFunctionDefinitions([])
      }
    }

    loadNodeDefinitions()
    return () => { isActive = false }
  }, [])

  return (
    <>
      <Section title="Function Type">
        <Field label="Type">
          <Select
            value={cfg.function_type}
            onChange={v => set('function_type', v)}
            disabled
            options={functionDefinitions.map(definition => ({
              value: definition.subtype,
              label: definition.label,
            }))}
          />
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            Type is locked after node creation.
          </p>
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

const CommunicationNodeConfig = ({ config, onChange }) => {
  const cfg = config || {}
  const set = (key, val) => onChange({ ...cfg, [key]: val })
  const setNested = (section, key, val) => onChange({ ...cfg, [section]: { ...(cfg[section] || {}), [key]: val } })
  const [communicationDefinitions, setCommunicationDefinitions] = useState([])

  useEffect(() => {
    let isActive = true

    const loadNodeDefinitions = async () => {
      try {
        const definitions = await getNodeDefinitions()
        if (!isActive) return
        setCommunicationDefinitions(
          definitions.filter(definition => definition.type === 'communication' && definition.show_in_frontend !== false)
        )
      } catch (_error) {
        if (!isActive) return
        setCommunicationDefinitions([])
      }
    }

    loadNodeDefinitions()
    return () => { isActive = false }
  }, [])

  return (
    <>
      <Section title="Communication Type">
        <Field label="Type">
          <Select
            value={cfg.communication_type}
            onChange={v => set('communication_type', v)}
            disabled
            options={communicationDefinitions.map(definition => ({
              value: definition.subtype,
              label: definition.label,
            }))}
          />
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
            Type is locked after node creation.
          </p>
        </Field>
      </Section>

      {(cfg.communication_type === 'rabbitmq_message' || !cfg.communication_type) && (
        <Section title="RabbitMQ">
          <Field label="Host">
            <Input value={cfg.rabbitmq_message?.host} onChange={v => setNested('rabbitmq_message', 'host', v)} placeholder="localhost" />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Port">
              <Input type="number" value={cfg.rabbitmq_message?.port ?? 5672} onChange={v => setNested('rabbitmq_message', 'port', v === '' ? '' : parseInt(v, 10))} placeholder="5672" />
            </Field>
            <Field label="Queue">
              <Input value={cfg.rabbitmq_message?.queue} onChange={v => setNested('rabbitmq_message', 'queue', v)} placeholder="events.queue" />
            </Field>
          </div>
          <Field label="Exchange">
            <Input value={cfg.rabbitmq_message?.exchange} onChange={v => setNested('rabbitmq_message', 'exchange', v)} placeholder="events.exchange" />
          </Field>
          <Field label="Routing Key">
            <Input value={cfg.rabbitmq_message?.routing_key} onChange={v => setNested('rabbitmq_message', 'routing_key', v)} placeholder="events.created" />
          </Field>
          <Field label="Output Key">
            <Input value={cfg.rabbitmq_message?.output_key} onChange={v => setNested('rabbitmq_message', 'output_key', v)} placeholder="rabbitmq_result" />
          </Field>
          <Field label="Payload Template (JSON)">
            <textarea
              value={cfg.rabbitmq_message?.payload_template || ''}
              onChange={e => setNested('rabbitmq_message', 'payload_template', e.target.value)}
              rows={4}
              placeholder='{"event":"created","input":{{input | tojson}}}'
              className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </Field>
        </Section>
      )}

      {cfg.communication_type === 'kafka' && (
        <Section title="Kafka">
          <Field label="Bootstrap Servers">
            <Input value={cfg.kafka?.bootstrap_servers} onChange={v => setNested('kafka', 'bootstrap_servers', v)} placeholder="localhost:9092" />
          </Field>
          <Field label="Topic">
            <Input value={cfg.kafka?.topic} onChange={v => setNested('kafka', 'topic', v)} placeholder="events.topic" />
          </Field>
          <Field label="Key Template">
            <Input value={cfg.kafka?.key_template} onChange={v => setNested('kafka', 'key_template', v)} placeholder="{{user_id}}" />
          </Field>
          <Field label="Output Key">
            <Input value={cfg.kafka?.output_key} onChange={v => setNested('kafka', 'output_key', v)} placeholder="kafka_result" />
          </Field>
          <Field label="Payload Template (JSON)">
            <textarea
              value={cfg.kafka?.payload_template || ''}
              onChange={e => setNested('kafka', 'payload_template', e.target.value)}
              rows={4}
              placeholder='{"event":"created","input":{{input | tojson}}}'
              className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </Field>
        </Section>
      )}

      {cfg.communication_type === 'api' && (
        <Section title="Communication API">
          <Field label="URL (supports {{state.key}})">
            <Input value={cfg.api?.url} onChange={v => setNested('api', 'url', v)} placeholder="https://hooks.example.com/events" />
          </Field>
          <Field label="Method">
            <Select value={cfg.api?.method || 'POST'} onChange={v => setNested('api', 'method', v)} options={[
              { value: 'POST', label: 'POST' },
              { value: 'PUT', label: 'PUT' },
              { value: 'PATCH', label: 'PATCH' },
            ]} />
          </Field>
          <Field label="Output Key">
            <Input value={cfg.api?.output_key} onChange={v => setNested('api', 'output_key', v)} placeholder="api_result" />
          </Field>
          <Field label="Body Template (JSON)">
            <textarea
              value={cfg.api?.body_template || ''}
              onChange={e => setNested('api', 'body_template', e.target.value)}
              rows={4}
              placeholder='{"message":{{input | tojson}}}'
              className="w-full px-3 py-2 rounded-lg text-sm font-mono outline-none resize-none"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </Field>
        </Section>
      )}
    </>
  )
}

// ─── Edge Config Panel ─────────────────────────────────────────────────────────

const EdgeConfigPanel = ({ edge, onClose }) => {
  const { nodes, updateEdgeData, removeEdge } = useGraphStore()
  const [config, setConfig] = useState(edge.data?.condition_config || {})
  const [label, setLabel] = useState(edge.data?.label || '')
  const [edgeType, setEdgeType] = useState(edge.data?.edge_type || 'direct')
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
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

  const handleDelete = async () => {
    setDeleting(true)
    try {
      await deleteEdge(edge.id)
      removeEdge(edge.id)
      onClose()
      toast.success('Edge deleted')
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Failed to delete edge')
    }
    setDeleting(false)
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div>
          <p className="text-xs font-mono uppercase tracking-widest" style={{ color: '#f59e0b' }}>Edge Config</p>
          <p className="text-sm font-semibold text-white mt-0.5">{sourceName} → {targetName}</p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handleDelete}
            disabled={deleting || saving}
            className="p-1.5 rounded hover:bg-red-900/30 transition-colors disabled:opacity-50"
            title="Delete edge"
          >
            <Trash2 size={14} style={{ color: '#ef4444' }} />
          </button>
          <button onClick={onClose}><X size={16} style={{ color: 'var(--text-muted)' }} /></button>
        </div>
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

      <div className="p-4 border-t flex gap-3" style={{ borderColor: 'var(--border)' }}>
        <button
          onClick={handleDelete}
          disabled={deleting || saving}
          className="px-4 py-2 rounded-lg text-sm font-semibold transition-opacity disabled:opacity-50"
          style={{ background: '#7f1d1d', color: '#fecaca' }}
        >
          {deleting ? 'Deleting...' : 'Delete Edge'}
        </button>
        <button
          onClick={handleSave}
          disabled={saving || deleting}
          className="flex-1 py-2 rounded-lg text-sm font-semibold transition-opacity"
          style={{ background: '#f59e0b', color: '#000', opacity: saving || deleting ? 0.6 : 1 }}
        >
          {saving ? 'Saving...' : 'Save Edge'}
        </button>
      </div>
    </div>
  )
}

// ─── Main Config Panel ─────────────────────────────────────────────────────────

export const ConfigPanel = ({ onClosePanel, panelWidth = 320, onDuplicateNode }) => {
  const { selectedNode, selectedEdge, clearSelection, agent, edges, updateNodeData, removeNode, setAgent } = useGraphStore()
  const [config, setConfig] = useState({})
  const [name, setName] = useState('')
  const [saving, setSaving] = useState(false)
  const [duplicating, setDuplicating] = useState(false)

  useEffect(() => {
    if (selectedNode) {
      const rawConfig = selectedNode.data?.config || {}
      const normalizedConfig = selectedNode.type === 'llmNode'
        ? {
            ...rawConfig,
            llm_type: selectedNode.data?.subtype || rawConfig.llm_type || (rawConfig.llm_runtime === 'agent' ? 'llm_agent' : 'chat'),
          }
        : rawConfig
      setConfig(normalizedConfig)
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
  const isCommunication = selectedNode.type === 'communicationNode'
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
        const normalizedConfig = normalizeNodeConfigForSave(selectedNode, config)
        const nextSubtype = nodeData.type === 'functional'
          ? (normalizedConfig.function_type || 'python_inline')
          : nodeData.type === 'communication'
            ? (normalizedConfig.communication_type || 'rabbitmq_message')
            : (normalizedConfig.llm_type || nodeData.subtype || 'chat')
        await updateNode(nodeData.id, { name, config: normalizedConfig, subtype: nextSubtype })
        updateNodeData(nodeId, { name, config: normalizedConfig, subtype: nextSubtype, label: name })
        if (name !== nodeName && agent) {
          const nextExitNodes = exitNodes.map(exitName => exitName === nodeName ? name : exitName)
          setAgent({
            ...agent,
            entry_node: agent.entry_node === nodeName ? name : agent.entry_node,
            exit_nodes: nextExitNodes,
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

  const handleDuplicate = async () => {
    if (!onDuplicateNode) return

    setDuplicating(true)
    try {
      await onDuplicateNode({
        node: selectedNode,
        draftName: name,
        draftConfig: config,
      })
    } finally {
      setDuplicating(false)
    }
  }

  return (
    <div
      className="flex flex-col h-full"
      style={{ width: `${panelWidth}px`, background: 'var(--surface)', borderLeft: '1px solid var(--border)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b" style={{ borderColor: 'var(--border)' }}>
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg" style={{ background: isLLM ? '#7c3aed22' : (isCommunication ? '#f9731622' : '#0ea5e922') }}>
            {isLLM ? <Brain size={14} style={{ color: '#7c3aed' }} /> : (isCommunication ? <RadioTower size={14} style={{ color: '#f97316' }} /> : <Zap size={14} style={{ color: '#0ea5e9' }} />)}
          </div>
          <div>
            <p className="text-xs font-mono uppercase tracking-widest" style={{ color: isLLM ? '#a78bfa' : (isCommunication ? '#fdba74' : '#38bdf8') }}>
              {isLLM ? 'LLM Node' : (isCommunication ? 'Communication Node' : 'Functional Node')}
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
        <button
          onClick={handleDuplicate}
          disabled={duplicating || saving}
          title="Create a copy of this node"
          className="flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors hover:opacity-80 disabled:opacity-50"
          style={{
            background: 'var(--surface2)',
            color: 'var(--text-muted)',
            border: '1px solid var(--border2)',
          }}
        >
          <Copy size={10} /> {duplicating ? 'Copying...' : 'Copy'}
        </button>
      </div>

      {/* Config form */}
      <div className="flex-1 overflow-y-auto">
        {isLLM
          ? <LLMNodeConfig config={config} onChange={setConfig} />
          : isCommunication
            ? <CommunicationNodeConfig config={config} onChange={setConfig} />
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
