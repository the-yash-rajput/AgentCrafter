import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Send } from 'lucide-react'
import { getAgent, getSession, runInSession, getRun } from '../../api/client'

const OUTPUT_KEYS = ['final_answer', 'response', 'output', 'message', 'reply', 'answer']

const extractResponse = (outputData) => {
  if (!outputData || typeof outputData !== 'object') return null
  for (const key of OUTPUT_KEYS) {
    if (outputData[key] && typeof outputData[key] === 'string' && outputData[key].trim()) {
      return outputData[key].trim()
    }
  }
  // fallback: first non-empty string value
  for (const val of Object.values(outputData)) {
    if (val && typeof val === 'string' && val.trim()) return val.trim()
  }
  return null
}

const pollRun = async (runId, maxAttempts = 60, intervalMs = 1000) => {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, intervalMs))
    const run = await getRun(runId)
    if (run.status === 'success' || run.status === 'failed') {
      return run
    }
  }
  throw new Error('Run timed out')
}

const Message = ({ role, content, error }) => {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className="max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed"
        style={{
          background: isUser ? '#6366f1' : (error ? '#ef444422' : 'var(--surface)'),
          color: isUser ? '#fff' : (error ? '#ef4444' : 'var(--text)'),
          border: isUser ? 'none' : `1px solid ${error ? '#ef444444' : 'var(--border2)'}`,
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {content}
      </div>
    </div>
  )
}

const TypingIndicator = () => (
  <div className="flex justify-start mb-4">
    <div
      className="px-4 py-3 rounded-2xl"
      style={{ background: 'var(--surface)', border: '1px solid var(--border2)', borderRadius: '18px 18px 18px 4px' }}
    >
      <div className="flex gap-1 items-center h-4">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-1.5 h-1.5 rounded-full animate-bounce"
            style={{ background: 'var(--text-muted)', animationDelay: `${i * 0.15}s` }}
          />
        ))}
      </div>
    </div>
  </div>
)

export const ChatPage = () => {
  const { agentId, versionId, sessionId } = useParams()
  const navigate = useNavigate()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [typing, setTyping] = useState(false)
  const [agentName, setAgentName] = useState('')
  const [versionNumber, setVersionNumber] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, typing, scrollToBottom])

  useEffect(() => {
    const loadSession = async () => {
      try {
        const [session, agent] = await Promise.all([
          getSession(agentId, versionId, sessionId),
          getAgent(agentId).catch(() => null),
        ])
        setVersionNumber(session.version_id)
        if (agent?.name) setAgentName(agent.name)

        // Build message list from conversation_history
        const history = session.conversation_history || []
        const msgs = history.map(msg => ({
          role: msg.role,
          content: msg.content,
        }))
        setMessages(msgs)
      } catch {
        setMessages([])
      }
      setLoading(false)
    }
    loadSession()
  }, [agentId, versionId, sessionId])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || typing) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setTyping(true)

    try {
      const run = await runInSession(agentId, versionId, sessionId, { message: text })
      const completedRun = await pollRun(run.id)

      if (completedRun.status === 'failed') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedRun.error || 'An error occurred.',
          error: true,
        }])
      } else {
        const response = extractResponse(completedRun.output_data)
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: response || 'Done.',
        }])
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: e.message || 'Something went wrong.',
        error: true,
      }])
    }

    setTyping(false)
  }, [agentId, input, sessionId, typing, versionId])

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }, [sendMessage])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg)' }}>
        <div className="w-6 h-6 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <div
        className="flex items-center gap-3 px-4 py-3 border-b shrink-0"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)', height: '52px' }}
      >
        <button
          onClick={() => navigate(`/agents/${agentId}/version/${versionId}/edit`)}
          className="p-1.5 rounded-lg hover:opacity-80 transition-opacity"
          style={{ color: 'var(--text-muted)' }}
        >
          <ArrowLeft size={16} />
        </button>
        <div className="w-px h-5" style={{ background: 'var(--border)' }} />
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-white">
            {agentName || `Agent ${agentId}`}
          </span>
          {versionNumber && (
            <span
              className="text-xs px-2 py-0.5 rounded font-mono"
              style={{ background: 'var(--surface2)', color: 'var(--text-muted)', border: '1px solid var(--border2)' }}
            >
              v{versionNumber}
            </span>
          )}
          <span
            className="text-xs px-2 py-0.5 rounded font-mono"
            style={{ background: '#6366f122', color: '#a5b4fc', border: '1px solid #818cf844' }}
          >
            session #{sessionId}
          </span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-2xl mx-auto">
          {messages.length === 0 && (
            <div className="text-center mt-16" style={{ color: 'var(--text-muted)' }}>
              <p className="text-sm">Send a message to start the conversation.</p>
            </div>
          )}
          {messages.map((msg, i) => (
            <Message key={i} role={msg.role} content={msg.content} error={msg.error} />
          ))}
          {typing && <TypingIndicator />}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input */}
      <div
        className="shrink-0 px-4 py-3 border-t"
        style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}
      >
        <div className="max-w-2xl mx-auto flex gap-2 items-end">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message... (Enter to send, Shift+Enter for newline)"
            rows={1}
            disabled={typing}
            className="flex-1 px-4 py-2.5 rounded-xl text-sm resize-none outline-none"
            style={{
              background: 'var(--bg)',
              border: '1px solid var(--border2)',
              color: 'var(--text)',
              maxHeight: '160px',
              overflowY: 'auto',
              lineHeight: '1.5',
            }}
            onInput={e => {
              e.target.style.height = 'auto'
              e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`
            }}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || typing}
            className="p-2.5 rounded-xl transition-all hover:opacity-80 disabled:opacity-40"
            style={{ background: '#6366f1', color: '#fff' }}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
