import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Loader, Send } from 'lucide-react'
import toast from 'react-hot-toast'
import { getAgent, getAgentSession, resolveAgentVersion, runAgentSession } from '../../api/client'

const normalizeMessages = (messages) => (
  Array.isArray(messages)
    ? messages
      .filter(message => (
        message &&
        typeof message === 'object' &&
        ['user', 'assistant', 'system'].includes(message.role) &&
        typeof message.content === 'string' &&
        message.content.trim()
      ))
      .map(message => ({
        role: message.role,
        content: message.content.trim(),
      }))
    : []
)

const MessageBubble = ({ message }) => {
  const isUser = message.role === 'user'
  const isSystem = message.role === 'system'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className="max-w-[780px] rounded-2xl px-4 py-3 text-sm whitespace-pre-wrap break-words"
        style={{
          background: isUser ? '#2563eb' : (isSystem ? '#78350f' : 'var(--surface)'),
          border: isUser ? '1px solid #60a5fa' : '1px solid var(--border2)',
          color: '#f8fafc',
          boxShadow: isUser ? '0 12px 28px rgba(37,99,235,0.24)' : 'none',
        }}
      >
        <div className="text-[10px] font-mono uppercase tracking-widest mb-1 opacity-70">
          {message.role}
        </div>
        {message.content}
      </div>
    </div>
  )
}

export const ChatSession = () => {
  const { agentId, versionId, sessionId } = useParams()
  const navigate = useNavigate()
  const [agent, setAgent] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [latestRun, setLatestRun] = useState(null)
  const [resolvedVersionId, setResolvedVersionId] = useState(null)

  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true)
      try {
        const resolvedVersion = await resolveAgentVersion(agentId, versionId)
        const [agentData, sessionData] = await Promise.all([
          getAgent(agentId, resolvedVersion.id),
          getAgentSession(agentId, resolvedVersion.id, sessionId),
        ])
        if (!active) return
        setResolvedVersionId(resolvedVersion.id)
        setAgent(agentData)
        setMessages(normalizeMessages(sessionData.conversation_history))
        if (String(versionId) !== String(resolvedVersion.version_number)) {
          navigate(`/agents/${agentId}/version/${resolvedVersion.version_number}/session/${sessionId}`, { replace: true })
        }
      } catch (_error) {
        if (!active) return
        toast.error('Failed to load chat session')
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [agentId, versionId, sessionId])

  const handleSend = async () => {
    const trimmed = input.trim()
    if (!trimmed || running || !resolvedVersionId) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: trimmed }])
    setRunning(true)
    try {
      const run = await runAgentSession(agentId, resolvedVersionId, sessionId, {
        input_data: {
          input: trimmed,
          message: trimmed,
        },
      })
      setLatestRun(run)
      setMessages(normalizeMessages(run.conversation_history))
      if (run.status === 'failed') {
        toast.error(run.error || 'Run failed')
      }
    } catch (error) {
      const detail = error.response?.data?.detail
      toast.error(typeof detail === 'object' ? JSON.stringify(detail) : (detail || 'Run failed'))
      setMessages(prev => prev.filter((message, index) => index !== prev.length - 1 || message.role !== 'user'))
    } finally {
      setRunning(false)
    }
  }

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center" style={{ background: 'var(--bg)' }}>
        <Loader size={28} className="animate-spin" style={{ color: '#60a5fa' }} />
      </div>
    )
  }

  return (
    <div className="h-screen flex flex-col" style={{ background: 'radial-gradient(circle at top left, #0f2a44 0, var(--bg) 36%, #070b13 100%)' }}>
      <div className="h-14 px-4 flex items-center gap-3 border-b" style={{ background: 'rgba(15,23,42,0.82)', borderColor: 'var(--border)' }}>
        <button
          onClick={() => navigate(`/agents/${agentId}/version/${agent?.version_number || versionId}/edit`)}
          className="p-1.5 rounded-lg hover:opacity-80"
          style={{ color: 'var(--text-muted)' }}
        >
          <ArrowLeft size={16} />
        </button>
        <div>
          <h1 className="text-sm font-semibold text-white">{agent?.name || 'Agent Chat'}</h1>
          <p className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
            Version {agent?.version_number || versionId} · Session #{sessionId}
            {latestRun?.id ? ` · Run #${latestRun.id}` : ''}
          </p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-4xl mx-auto space-y-4">
          {messages.length ? (
            messages.map((message, index) => (
              <MessageBubble key={`${message.role}-${index}-${message.content}`} message={message} />
            ))
          ) : (
            <div className="text-center mt-24">
              <p className="text-lg font-semibold text-white">Start this session</p>
              <p className="text-sm mt-2" style={{ color: 'var(--text-muted)' }}>
                Each message creates a run under session #{sessionId}.
              </p>
            </div>
          )}
          {running && (
            <div className="flex justify-start">
              <div className="rounded-2xl px-4 py-3 flex items-center gap-2" style={{ background: 'var(--surface)', border: '1px solid var(--border2)' }}>
                <Loader size={14} className="animate-spin" style={{ color: '#60a5fa' }} />
                <span className="text-sm" style={{ color: 'var(--text-muted)' }}>Running agent...</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="px-4 py-4 border-t" style={{ borderColor: 'var(--border)', background: 'rgba(15,23,42,0.86)' }}>
        <div className="max-w-4xl mx-auto flex gap-3">
          <textarea
            value={input}
            onChange={event => setInput(event.target.value)}
            onKeyDown={event => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                handleSend()
              }
            }}
            rows={2}
            placeholder="Message the agent..."
            className="flex-1 resize-none rounded-2xl px-4 py-3 text-sm outline-none"
            style={{ background: 'var(--surface)', border: '1px solid var(--border2)', color: 'var(--text)' }}
          />
          <button
            onClick={handleSend}
            disabled={running || !input.trim()}
            className="w-12 rounded-2xl flex items-center justify-center disabled:opacity-50"
            style={{ background: '#2563eb', color: '#fff' }}
          >
            {running ? <Loader size={16} className="animate-spin" /> : <Send size={16} />}
          </button>
        </div>
      </div>
    </div>
  )
}
