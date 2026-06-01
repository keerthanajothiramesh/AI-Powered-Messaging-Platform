import { useState, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Send, Bot, Loader2, Sparkles } from 'lucide-react'
import client from '../api/client'

export default function AIAssistantPanel({ onClose }) {
  const { t } = useTranslation()
  const [messages, setMessages] = useState([
    { role: 'bot', text: 'Hi! I\'m your AI assistant. Ask me to search messages, summarise conversations, or find media.', toolCalls: [] }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages.length])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages((m) => [...m, { role: 'user', text, ts: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }])
    setLoading(true)
    try {
      const res = await client.post('/ai/chat', { message: text })
      setMessages((m) => [...m, {
        role: 'bot',
        text: res.data.text,
        toolCalls: res.data.tool_calls || [],
        ts: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      }])
    } catch {
      setMessages((m) => [...m, { role: 'bot', text: 'Sorry, something went wrong. Please try again.', toolCalls: [] }])
    } finally {
      setLoading(false)
    }
  }

  const handleExample = (example) => setInput(example)

  return (
    <div className="w-80 flex flex-col bg-white border-l border-slate-100 shadow-xl flex-shrink-0">
      {/* Header */}
      <div className="px-4 py-4 flex items-center justify-between"
           style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}>
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-xl bg-white/20 flex items-center justify-center">
            <Bot size={17} className="text-white" />
          </div>
          <div>
            <span className="font-semibold text-white text-sm">{t('ai.assistant')}</span>
            <p className="text-white/60 text-xs">Powered by OpenAI</p>
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 hover:bg-white/20 rounded-lg transition-all">
          <X size={16} className="text-white" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin" style={{ background: 'linear-gradient(to bottom, #f8faff, #ffffff)' }}>
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[90%] ${msg.role === 'user' ? '' : 'w-full'}`}>
              {msg.role === 'bot' && (
                <div className="flex items-center gap-1 mb-1.5">
                  <Sparkles size={11} className="text-indigo-500" />
                  <span className="text-xs text-indigo-500 font-semibold">AI</span>
                </div>
              )}
              <div className={`rounded-2xl px-3 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'text-white rounded-br-sm shadow-md'
                  : 'bg-slate-50 text-slate-800 border border-slate-100 rounded-bl-sm'
              }`}
              style={msg.role === 'user' ? { background: 'linear-gradient(135deg, #6366f1, #7c3aed)' } : {}}>
                <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.text}</p>
                {msg.ts && <p className={`text-xs mt-1 ${msg.role === 'user' ? 'text-white/60 text-right' : 'text-slate-400'}`}>{msg.ts}</p>}
              </div>
              {msg.toolCalls?.length > 0 && (
                <div className="mt-2 space-y-1">
                  {msg.toolCalls.map((tc, j) => (
                    <ToolCallCard key={j} toolCall={tc} />
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-2 text-indigo-400 text-sm">
            <Loader2 size={14} className="animate-spin" />
            {t('ai.thinking')}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick examples */}
      <div className="px-3 py-2.5 border-t border-slate-100" style={{ background: 'linear-gradient(to bottom, #f0f4ff, #ffffff)' }}>
        <p className="text-xs text-slate-500 mb-2 font-semibold">Quick examples:</p>
        <div className="space-y-1">
          {Object.values(t('ai.examples', { returnObjects: true })).map((ex, i) => (
            <button
              key={i}
              onClick={() => handleExample(ex)}
              className="w-full text-left text-xs text-indigo-600 hover:bg-indigo-50 px-2 py-1.5 rounded-lg transition-all truncate font-medium"
            >
              "{ex}"
            </button>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="p-3 border-t border-slate-100 bg-white">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={t('ai.placeholder')}
            className="flex-1 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-all"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="p-2.5 text-white rounded-xl disabled:opacity-40 transition-all shadow-sm"
            style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
          >
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  )
}

function ToolCallCard({ toolCall }) {
  const [expanded, setExpanded] = useState(false)
  const resultCount = Array.isArray(toolCall.result)
    ? toolCall.result.length
    : toolCall.result?.summary ? 1 : 0

  return (
    <div className="bg-white border border-indigo-100 rounded-xl overflow-hidden shadow-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-slate-600 hover:bg-indigo-50/50 transition-all"
      >
        <span className="font-semibold text-indigo-600">🔧 {toolCall.tool}</span>
        <span className="text-slate-400">{resultCount} results {expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && toolCall.result && (
        <div className="px-3 pb-2 space-y-1">
          {Array.isArray(toolCall.result)
            ? toolCall.result.slice(0, 3).map((r, i) => (
                <div key={i} className="text-xs text-slate-600 bg-indigo-50/50 rounded-lg p-1.5">
                  <p className="truncate">{r.content || JSON.stringify(r).slice(0, 80)}</p>
                  {r.media_url && (
                    <a
                      href={r.media_url.startsWith('http') ? r.media_url : `${import.meta.env.VITE_API_URL || 'http://localhost:8000'}${r.media_url}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 mt-1 text-indigo-600 font-semibold hover:underline"
                    >
                      📎 Open {r.media_type || 'file'}
                    </a>
                  )}
                </div>
              ))
            : <p className="text-xs text-slate-600">{toolCall.result?.summary || JSON.stringify(toolCall.result).slice(0, 100)}</p>
          }
        </div>
      )}
    </div>
  )
}
