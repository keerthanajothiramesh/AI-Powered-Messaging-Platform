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
    setMessages((m) => [...m, { role: 'user', text }])
    setLoading(true)
    try {
      const res = await client.post('/ai/chat', { message: text })
      setMessages((m) => [...m, {
        role: 'bot',
        text: res.data.text,
        toolCalls: res.data.tool_calls || [],
      }])
    } catch (err) {
      setMessages((m) => [...m, { role: 'bot', text: 'Sorry, something went wrong. Please try again.', toolCalls: [] }])
    } finally {
      setLoading(false)
    }
  }

  const handleExample = (example) => setInput(example)

  return (
    <div className="w-80 flex flex-col bg-white border-l border-gray-100 shadow-xl">
      <div className="px-4 py-4 border-b border-gray-100 flex items-center justify-between bg-primary text-white">
        <div className="flex items-center gap-2">
          <Bot size={20} />
          <span className="font-semibold">{t('ai.assistant')}</span>
        </div>
        <button onClick={onClose} className="hover:opacity-70 transition-opacity">
          <X size={18} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 scrollbar-thin">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[90%] ${msg.role === 'user' ? '' : 'w-full'}`}>
              {msg.role === 'bot' && (
                <div className="flex items-center gap-1 mb-1">
                  <Sparkles size={12} className="text-primary" />
                  <span className="text-xs text-gray-500 font-medium">AI</span>
                </div>
              )}
              <div className={`rounded-xl px-3 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-primary text-white rounded-br-sm'
                  : 'bg-gray-50 text-gray-800 border border-gray-100 rounded-bl-sm'
              }`}>
                <p className="whitespace-pre-wrap break-words">{msg.text}</p>
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
          <div className="flex items-center gap-2 text-gray-400 text-sm">
            <Loader2 size={14} className="animate-spin" />
            {t('ai.thinking')}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="px-3 py-2 border-t border-gray-100 bg-gray-50">
        <p className="text-xs text-gray-500 mb-2 font-medium">Quick examples:</p>
        <div className="space-y-1">
          {Object.values(t('ai.examples', { returnObjects: true })).map((ex, i) => (
            <button
              key={i}
              onClick={() => handleExample(ex)}
              className="w-full text-left text-xs text-primary hover:bg-red-50 px-2 py-1 rounded-lg transition-colors truncate"
            >
              "{ex}"
            </button>
          ))}
        </div>
      </div>

      <div className="p-3 border-t border-gray-100">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={t('ai.placeholder')}
            className="flex-1 px-3 py-2 bg-gray-50 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || loading}
            className="p-2 bg-primary text-white rounded-lg disabled:opacity-40 hover:bg-primary-dark transition-colors"
          >
            <Send size={16} />
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
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-600 hover:bg-gray-50"
      >
        <span className="font-medium">🔧 {toolCall.tool}</span>
        <span className="text-gray-400">{resultCount} results {expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && toolCall.result && (
        <div className="px-3 pb-2 space-y-1">
          {Array.isArray(toolCall.result)
            ? toolCall.result.slice(0, 3).map((r, i) => (
                <p key={i} className="text-xs text-gray-600 bg-gray-50 rounded p-1 truncate">
                  {r.content || JSON.stringify(r).slice(0, 80)}
                </p>
              ))
            : <p className="text-xs text-gray-600">{toolCall.result?.summary || JSON.stringify(toolCall.result).slice(0, 100)}</p>
          }
        </div>
      )}
    </div>
  )
}
