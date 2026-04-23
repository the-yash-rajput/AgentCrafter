import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Send, Square } from 'lucide-react'
import { getAgent, getSession, runInSession, getRun, resumeRun, pauseRun } from '../../api/client'

const normalizeMessageContent = (content) => {
  if (typeof content === 'string') return content
  if (content == null) return ''

  try {
    return JSON.stringify(content)
  } catch {
    return String(content)
  }
}

const normalizeChatMessages = (history) => {
  if (!Array.isArray(history)) return []

  return history
    .filter(message => message && typeof message === 'object')
    .map(message => ({
      role: message.role,
      content: normalizeMessageContent(message.content).trim(),
    }))
    .filter(message => ['user', 'assistant', 'system'].includes(message.role) && message.content)
}

const areSameMessage = (left, right) => left?.role === right?.role && left?.content === right?.content

const mergeChatMessages = (baseHistory, additionalHistory = []) => {
  const base = normalizeChatMessages(baseHistory)
  const additional = normalizeChatMessages(additionalHistory)

  if (base.length === 0) return additional
  if (additional.length === 0) return base

  const suffixStart = base.length - additional.length
  if (
    suffixStart >= 0 &&
    additional.every((message, index) => areSameMessage(base[suffixStart + index], message))
  ) {
    return base
  }

  for (let overlap = Math.min(base.length, additional.length); overlap > 0; overlap -= 1) {
    const matches = additional
      .slice(0, overlap)
      .every((message, index) => areSameMessage(base[base.length - overlap + index], message))

    if (matches) {
      return [...base, ...additional.slice(overlap)]
    }
  }

  return [...base, ...additional]
}

const loadCompletedMessages = async ({
  agentId,
  versionId,
  sessionId,
  completedRun,
  fallbackHistory,
}) => {
  const runTurn = normalizeChatMessages(completedRun?.conversation_turn)

  try {
    const updatedSession = await getSession(agentId, versionId, sessionId)
    return mergeChatMessages(updatedSession?.conversation_history, runTurn)
  } catch {
    return mergeChatMessages(fallbackHistory, runTurn)
  }
}

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

const Message = ({ role, content, error, interrupted, paused, runId, onResume, interruptMetadata }) => {
  const isUser = role === 'user'
  const isConfidenceCheck = interruptMetadata?.interrupt_type === 'confidence_check'
  const [humanResponseInput, setHumanResponseInput] = useState('')

  const handleResume = () => {
    if (isConfidenceCheck) {
      // If user typed an override, send it; otherwise approve the original LLM response
      const value = humanResponseInput.trim() || interruptMetadata.llm_response
      onResume(runId, value)
    } else {
      onResume(runId)
    }
  }

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

        {interrupted && isConfidenceCheck && interruptMetadata && (
          <div className="mt-3 text-xs" style={{ color: 'var(--text-muted)' }}>
            <div className="mb-2 font-mono" style={{ color: '#f59e0b' }}>
              Node: <strong>{interruptMetadata.node_name}</strong> &nbsp;|&nbsp;
              Confidence: <strong>{Math.round((interruptMetadata.confidence ?? 0) * 100)}%</strong> &lt; threshold{' '}
              <strong>{Math.round((interruptMetadata.threshold ?? 0) * 100)}%</strong>
            </div>
            <div className="mb-2">
              <span style={{ color: 'var(--text-muted)' }}>LLM response:</span>
              <pre
                className="mt-1 p-2 rounded text-xs overflow-auto"
                style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)', maxHeight: '120px' }}
              >
                {typeof interruptMetadata.llm_response === 'object'
                  ? JSON.stringify(interruptMetadata.llm_response, null, 2)
                  : String(interruptMetadata.llm_response ?? '')}
              </pre>
            </div>
            <textarea
              value={humanResponseInput}
              onChange={e => setHumanResponseInput(e.target.value)}
              rows={3}
              placeholder="Override response (leave empty to approve the LLM's response above)"
              className="w-full px-2 py-1.5 rounded text-xs font-mono outline-none resize-none mb-2"
              style={{ background: 'var(--bg)', border: '1px solid var(--border2)', color: 'var(--text)' }}
            />
          </div>
        )}

        {interrupted && onResume && (
          <button
            onClick={handleResume}
            className="mt-2 flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg font-medium transition-opacity hover:opacity-80"
            style={{ background: '#6366f1', color: '#fff' }}
          >
            ↺ {isConfidenceCheck ? (humanResponseInput.trim() ? 'Resume with Override' : 'Approve & Resume') : 'Resume'}
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
  const messagesRef = useRef([])
  const textareaRef = useRef(null)
  const abortControllerRef = useRef(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    messagesRef.current = messages
  }, [messages])

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

        setMessages(normalizeChatMessages(session.conversation_history))
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

  const handleResume = useCallback(async (runId, humanResponse = null) => {
    setTyping(true)
    setMessages(prev => prev.filter(m => !(m.interrupted && m.runId === runId)))

    try {
      const resumePayload = humanResponse ? { human_response: humanResponse } : {}
      const newRun = await resumeRun(runId, resumePayload)
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
        const meta = completedRun.interrupt_metadata
        const isConfidence = meta?.interrupt_type === 'confidence_check'
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: isConfidence
            ? `Low confidence (${Math.round((meta.confidence ?? 0) * 100)}% < ${Math.round((meta.threshold ?? 0) * 100)}% threshold) — review the response below.`
            : 'Run was interrupted again.',
          error: !isConfidence,
          interrupted: true,
          runId: completedRun.id,
          interruptMetadata: meta || null,
        }])
      } else if (completedRun.status === 'failed') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedRun.error || 'An error occurred.',
          error: true,
        }])
      } else {
        const mergedMessages = await loadCompletedMessages({
          agentId,
          versionId,
          sessionId,
          completedRun,
          fallbackHistory: messagesRef.current,
        })
        setMessages(mergedMessages)
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
        const meta = completedRun.interrupt_metadata
        const isConfidence = meta?.interrupt_type === 'confidence_check'
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: isConfidence
            ? `Low confidence (${Math.round((meta.confidence ?? 0) * 100)}% < ${Math.round((meta.threshold ?? 0) * 100)}% threshold) — review the response below.`
            : 'Run was interrupted before completing.',
          error: !isConfidence,
          interrupted: true,
          runId: completedRun.id,
          interruptMetadata: meta || null,
        }])
      } else if (completedRun.status === 'failed') {
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: completedRun.error || 'An error occurred.',
          error: true,
        }])
      } else {
        const mergedMessages = await loadCompletedMessages({
          agentId,
          versionId,
          sessionId,
          completedRun,
          fallbackHistory: messagesRef.current,
        })
        setMessages(mergedMessages)
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
