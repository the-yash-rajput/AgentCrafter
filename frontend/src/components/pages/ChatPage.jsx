import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Send, Square } from 'lucide-react'
import { getAgent, getSession, runInSession, getRun, resumeRun, pauseRun } from '../../api/client'

const pollRun = async (runId, signal, maxAttempts = 60, intervalMs = 1000) => {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise(resolve => setTimeout(resolve, intervalMs))
    if (signal?.aborted) return null  // user paused — stop watching
    const run = await getRun(runId)
    if (['success', 'failed', 'interrupted'].includes(run.status)) {
      return run
    }
  }
  throw new Error('Run timed out')
}

const Message = ({ role, content, error, interrupted, paused, runId, onResume }) => {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className="max-w-[75%] px-4 py-3 rounded-2xl text-sm leading-relaxed"
        style={{
          background: isUser ? '#6366f1' : (error ? '#ef444422' : paused ? '#f59e0b22' : 'var(--surface)'),
          color: isUser ? '#fff' : (error ? '#ef4444' : paused ? '#f59e0b' : 'var(--text)'),
          border: isUser ? 'none' : `1px solid ${error ? '#ef444444' : paused ? '#f59e0b44' : 'var(--border2)'}`,
          borderRadius: isUser ? '18px 18px 4px 18px' : '18px 18px 18px 4px',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {content}
        {interrupted && onResume && (
          <button
            onClick={() => onResume(runId)}
            className="mt-2 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity hover:opacity-80"
            style={{ background: '#6366f1', color: '#fff' }}
          >
            ↺ Resume
          </button>
        )}
      </div>
    </div>
  )
}

const TypingIndicator = () => (
  <div className="flex justify-start">
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
  const [currentRunId, setCurrentRunId] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const abortControllerRef = useRef(null)

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

  const handlePause = useCallback(async () => {
    if (currentRunId) {
      try { await pauseRun(currentRunId) } catch (_) {}
      // Keep polling — when the run transitions to 'interrupted' the normal
      // flow will show the Resume button automatically.
    }
  }, [currentRunId])

  const handleResume = useCallback(async (runId) => {
    setTyping(true)
    setMessages(prev => prev.filter(m => !(m.interrupted && m.runId === runId)))

    try {
      const newRun = await resumeRun(runId)
      setCurrentRunId(newRun.id)

      const controller = new AbortController()
      abortControllerRef.current = controller
      const completedRun = await pollRun(newRun.id, controller.signal)

      if (completedRun === null) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Run is still executing in the background.',
          paused: true,
        }])
      } else if (completedRun.status === 'interrupted') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Run was interrupted again.',
          error: true,
          interrupted: true,
          runId: completedRun.id,
        }])
      } else if (completedRun.status === 'failed') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedRun.error || 'An error occurred.',
          error: true,
        }])
      } else {
        const updatedSession = await getSession(agentId, versionId, sessionId)
        const history = updatedSession.conversation_history || []
        setMessages(history.map(msg => ({ role: msg.role, content: msg.content })))
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: e.message || 'Resume failed.',
        error: true,
      }])
    }

    setTyping(false)
    setCurrentRunId(null)
  }, [agentId, versionId, sessionId])

  const sendMessage = useCallback(async () => {
    const text = input.trim()
    if (!text || typing) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setTyping(true)

    try {
      const run = await runInSession(agentId, versionId, sessionId, { message: text })
      setCurrentRunId(run.id)

      const controller = new AbortController()
      abortControllerRef.current = controller
      const completedRun = await pollRun(run.id, controller.signal)

      if (completedRun === null) {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Run is still executing in the background. You can resume monitoring when it completes.',
          paused: true,
        }])
      } else if (completedRun.status === 'interrupted') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: 'Run was interrupted before completing.',
          error: true,
          interrupted: true,
          runId: completedRun.id,
        }])
      } else if (completedRun.status === 'failed') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedRun.error || 'An error occurred.',
          error: true,
        }])
      } else {
        const updatedSession = await getSession(agentId, versionId, sessionId)
        const history = updatedSession.conversation_history || []
        setMessages(history.map(msg => ({ role: msg.role, content: msg.content })))
      }
    } catch (e) {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: e.message || 'Something went wrong.',
        error: true,
      }])
    }

    setTyping(false)
    setCurrentRunId(null)
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
            <Message key={i} {...msg} onResume={handleResume} />
          ))}
          {typing && (
            <div className="flex items-center gap-3 mb-4">
              <TypingIndicator />
              <button
                onClick={handlePause}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity hover:opacity-80"
                style={{ background: 'var(--surface)', border: '1px solid var(--border2)', color: 'var(--text-muted)' }}
                title="Stop watching this run"
              >
                <Square size={10} fill="currentColor" />
                Pause
              </button>
            </div>
          )}
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
