import { useState, useRef, useEffect } from 'react'
import { X, Sparkles, Send, Mic, Paperclip, Plus, MessageSquare, Bot, Loader2, HelpCircle } from 'lucide-react'
import client from '../api/client'
import AIHelpGuide from './AIHelpGuide'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const IMAGE_EXT = /\.(png|jpg|jpeg|gif|webp|svg)$/i

function resolveUrl(url) {
  if (!url) return ''
  return url.startsWith('http') ? url : `${API_BASE}${url}`
}

const EMOJIS = ['😊','👍','❤️','🎉','😂','🤔','👏','🙏','💡','✅','⚡','🔥','💯','🚀','📌','✨','🎯','👀']

const STARTERS = [
  '"What can this AI assistant do? ✨"',
  '"Search messages across all my conversations 🔍"',
  '"Summarize the most active group 📋"',
  '"Show me recent unread images 🖼️"',
]

function makeThread() {
  return {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
    name: 'New Chat',
    messages: [{
      role: 'bot',
      text: "Hi! I'm your global AI assistant. I can search across all your conversations, summarise groups, find images, or answer anything about your messages. What can I help with?",
    }],
  }
}

export default function GlobalBotDrawer({ onClose }) {
  const [threads, setThreads] = useState(() => {
    try {
      const s = localStorage.getItem('globalBotThreads')
      if (s) { const p = JSON.parse(s); if (Array.isArray(p) && p.length) return p }
    } catch {}
    return [makeThread()]
  })
  const [activeIdx, setActiveIdx] = useState(0)
  const [showThreads, setShowThreads] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const [showEmoji, setShowEmoji] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const bottomRef = useRef(null)
  const fileRef = useRef(null)
  const recRef = useRef(null)

  const safeIdx = Math.min(activeIdx, threads.length - 1)
  const thread = threads[safeIdx]
  const msgs = thread?.messages || []

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs.length])
  useEffect(() => {
    try { localStorage.setItem('globalBotThreads', JSON.stringify(threads.slice(-10))) } catch {}
  }, [threads])

  // Close on Escape
  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [onClose])

  const update = (idx, fn) =>
    setThreads(prev => { const n = [...prev]; n[idx] = fn(n[idx]); return n })

  const send = async (text) => {
    const t = (text || input).trim()
    if (!t || loading) return
    setInput(''); setShowEmoji(false)
    const ci = safeIdx
    update(ci, th => ({
      ...th,
      name: th.name === 'New Chat' ? t.slice(0, 30) : th.name,
      messages: [...th.messages, { role: 'user', text: t }],
    }))
    setLoading(true)
    try {
      const res = await client.post('/ai/chat', {
        message: t,
        session_id: threads[ci]?.id,
        conv_id: 'global',
        is_group: false,
        conv_name: 'Global Assistant',
      })
      update(ci, th => ({
        ...th,
        messages: [...th.messages, {
          role: 'bot',
          text: res.data.text || 'No response.',
          toolCalls: res.data.tool_calls || [],
        }],
      }))
    } catch {
      update(ci, th => ({
        ...th,
        messages: [...th.messages, { role: 'bot', text: '⚠️ Something went wrong. Please try again.' }],
      }))
    } finally { setLoading(false) }
  }

  const newThread = () => {
    const t = makeThread()
    setThreads(prev => [...prev, t])
    setActiveIdx(threads.length)
    setShowThreads(false)
  }

  const deleteThread = (idx, e) => {
    e.stopPropagation()
    if (threads.length === 1) { setThreads([makeThread()]); setActiveIdx(0); return }
    setThreads(prev => prev.filter((_, i) => i !== idx))
    setActiveIdx(prev => Math.max(0, prev >= idx ? prev - 1 : prev))
    setShowThreads(false)
  }

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    const rec = new SR(); rec.lang = 'en-US'; rec.interimResults = false
    rec.onresult = (e) => setInput(p => p + e.results[0][0].transcript + ' ')
    rec.onend = () => setListening(false)
    recRef.current = rec; rec.start(); setListening(true)
  }

  const handleFile = (e) => {
    const file = e.target.files[0]; if (!file) return
    const isText = file.type.startsWith('text/') || /\.(txt|md|csv|json|js|py|ts)$/i.test(file.name)
    if (isText) {
      const r = new FileReader()
      r.onload = (ev) => {
        const txt = ev.target.result
        send(`📎 [${file.name}]\n\n${txt.slice(0, 1500)}${txt.length > 1500 ? '\n...(truncated)' : ''}`)
      }
      r.readAsText(file)
    } else {
      send(`📎 Uploaded: **${file.name}** (${(file.size / 1024).toFixed(1)} KB)`)
    }
    e.target.value = ''
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Drawer */}
      <div
        className="fixed right-0 top-0 bottom-0 z-50 flex flex-col bg-white shadow-2xl"
        style={{ width: 'min(480px, 100vw)', animation: 'slideInRight 0.22s ease-out' }}
      >
        {/* Header */}
        <div
          className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 flex-shrink-0"
          style={{ background: 'linear-gradient(to right, #eef2ff, #ede9fe)' }}
        >
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center shadow-sm flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
          >
            <Bot size={15} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-indigo-700 truncate">
              {thread?.name || 'Global AI Assistant'}
            </p>
            <p className="text-xs text-slate-400">Powered by OpenAI ✨ · global context</p>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowThreads(v => !v)}
              className={`p-1.5 rounded-lg transition-all text-xs ${showThreads ? 'bg-indigo-100 text-indigo-600' : 'text-slate-400 hover:text-indigo-500 hover:bg-indigo-50'}`}
              title="All chats"
            >
              <MessageSquare size={14} />
            </button>
            <button
              onClick={newThread}
              className="p-1.5 text-slate-400 hover:text-indigo-500 hover:bg-indigo-50 rounded-lg transition-all"
              title="New chat"
            >
              <Plus size={14} />
            </button>
            <button
              onClick={() => setShowHelp(v => !v)}
              className={`p-1.5 rounded-lg transition-all ${showHelp ? 'bg-indigo-100 text-indigo-600' : 'text-slate-400 hover:text-indigo-500 hover:bg-indigo-50'}`}
              title="Feature guide"
            >
              <HelpCircle size={14} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {/* Thread list */}
        {showThreads && (
          <div className="border-b border-slate-100 bg-white shadow-sm flex-shrink-0">
            <div className="max-h-52 overflow-y-auto">
              {threads.map((th, i) => (
                <div
                  key={th.id}
                  onClick={() => { setActiveIdx(i); setShowThreads(false) }}
                  className={`flex items-center gap-2 px-4 py-2.5 cursor-pointer group transition-all ${i === safeIdx ? 'bg-indigo-50' : 'hover:bg-slate-50'}`}
                >
                  <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${i === safeIdx ? 'bg-indigo-500' : 'bg-slate-200'}`} />
                  <span className={`text-xs flex-1 truncate ${i === safeIdx ? 'text-indigo-700 font-semibold' : 'text-slate-600'}`}>
                    {th.name}
                  </span>
                  <button
                    onClick={(e) => deleteThread(i, e)}
                    className="text-slate-300 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all px-1 text-sm"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
            <div className="px-4 py-2 border-t border-slate-100">
              <button
                onClick={newThread}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
              >
                <Plus size={11} /> New Chat
              </button>
            </div>
          </div>
        )}

        {/* Messages or Help Guide */}
        {showHelp ? (
          <AIHelpGuide
            onSelect={(p) => { setInput(p); setShowHelp(false) }}
            onClose={() => setShowHelp(false)}
          />
        ) : (
          <>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {msgs.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                  <div className="max-w-[85%] flex flex-col gap-2">
                    <div
                      className={`text-sm rounded-2xl px-4 py-2.5 leading-relaxed ${
                        msg.role === 'user'
                          ? 'text-white rounded-br-sm shadow-sm'
                          : 'bg-slate-50 text-slate-700 border border-slate-100 rounded-bl-sm'
                      }`}
                      style={msg.role === 'user' ? { background: 'linear-gradient(135deg, #6366f1, #7c3aed)' } : {}}
                    >
                      {msg.role === 'bot' && (
                        <span className="flex items-center gap-1.5 mb-1.5">
                          <Sparkles size={10} className="text-indigo-400" />
                          <span className="text-xs text-indigo-500 font-semibold">AI ✨</span>
                        </span>
                      )}
                      <p className="whitespace-pre-wrap break-words">{msg.text}</p>
                    </div>
                    {msg.role === 'bot' && msg.toolCalls?.length > 0 && (
                      <BotToolResult toolCalls={msg.toolCalls} />
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex items-center gap-2 text-indigo-400 text-sm px-1">
                  <Loader2 size={13} className="animate-spin" /> Thinking…
                </div>
              )}
              <div ref={bottomRef} />
            </div>
            {msgs.length === 1 && (
              <div className="px-4 pb-2 space-y-1.5 flex-shrink-0">
                {STARTERS.map((s) => (
                  <button
                    key={s}
                    onClick={() => send(s.replace(/^"|"$/g, ''))}
                    className="w-full text-left text-xs text-indigo-600 hover:bg-indigo-50 px-3 py-2 rounded-xl transition-all font-medium"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </>
        )}

        {/* Input */}
        <div className="p-3 border-t border-slate-100 flex-shrink-0">
          {showEmoji && (
            <div className="mb-2 bg-white border border-slate-200 rounded-2xl p-2 grid grid-cols-9 gap-0.5 shadow-md">
              {EMOJIS.map(em => (
                <button
                  key={em}
                  onClick={() => { setInput(p => p + em); setShowEmoji(false) }}
                  className="text-lg hover:bg-slate-100 rounded-lg p-1 transition-all leading-none"
                >
                  {em}
                </button>
              ))}
            </div>
          )}
          <div className="flex gap-2 items-center">
            <button
              onClick={() => setShowEmoji(v => !v)}
              className={`p-1.5 rounded-xl transition-all flex-shrink-0 text-base leading-none ${showEmoji ? 'bg-indigo-50' : 'opacity-60 hover:opacity-100'}`}
            >
              😊
            </button>
            <button
              onClick={() => fileRef.current?.click()}
              className="p-1.5 text-slate-400 hover:text-indigo-500 rounded-xl transition-all flex-shrink-0"
              title="Attach file"
            >
              <Paperclip size={14} />
            </button>
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
              placeholder="Ask anything…"
              className="flex-1 min-w-0 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-all"
            />
            <button
              onClick={listening ? () => { recRef.current?.stop(); setListening(false) } : startVoice}
              className={`p-1.5 rounded-xl transition-all flex-shrink-0 ${listening ? 'text-red-500 bg-red-50 animate-pulse' : 'text-slate-400 hover:text-indigo-500 hover:bg-indigo-50'}`}
              title={listening ? 'Stop' : 'Voice input'}
            >
              <Mic size={14} />
            </button>
            <button
              onClick={() => send()}
              disabled={!input.trim() || loading}
              className="p-2 text-white rounded-xl disabled:opacity-40 transition-all flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
            >
              <Send size={13} />
            </button>
          </div>
          <input ref={fileRef} type="file" className="hidden" onChange={handleFile}
            accept=".txt,.md,.csv,.json,.js,.py,.ts" />
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);    opacity: 1; }
        }
      `}</style>
    </>
  )
}

function BotToolResult({ toolCalls }) {
  const images = []
  const files = []

  for (const { result } of toolCalls) {
    if (!result) continue

    // list_shared_documents → { documents: [{filename, ...}] }
    if (result.documents) {
      for (const doc of result.documents) {
        const url = `${API_BASE}/media/file/${encodeURIComponent(doc.filename)}`
        if (IMAGE_EXT.test(doc.filename)) {
          images.push({ url, name: doc.filename })
        } else {
          files.push({ url, name: doc.filename })
        }
      }
    }

    // Array results: find_media, fetch_unread_images, search_messages
    if (Array.isArray(result)) {
      for (const r of result) {
        if (!r.media_url) continue
        const url = resolveUrl(r.media_url)
        if (r.media_type === 'image' || IMAGE_EXT.test(r.content || '')) {
          images.push({ url, name: r.content || 'image' })
        } else if (r.media_type === 'document' || r.media_type === 'file') {
          files.push({ url, name: r.content || 'file' })
        }
      }
    }
  }

  if (!images.length && !files.length) return null

  return (
    <div className="space-y-2">
      {images.map((img, i) => (
        <div key={i} className="rounded-xl overflow-hidden border border-indigo-100 bg-slate-50 shadow-sm">
          <img
            src={img.url}
            alt={img.name}
            className="w-full max-h-56 object-contain cursor-pointer hover:opacity-90 transition-opacity"
            onClick={() => window.open(img.url, '_blank')}
            onError={(e) => { e.currentTarget.closest('div').style.display = 'none' }}
          />
          <p className="text-xs text-slate-400 px-3 py-1.5 truncate">{img.name}</p>
        </div>
      ))}
      {files.map((file, i) => (
        <a
          key={i}
          href={file.url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 px-3 py-2 bg-white border border-indigo-100 rounded-xl text-xs text-indigo-600 hover:bg-indigo-50 transition-all shadow-sm"
        >
          <span>📄</span>
          <span className="truncate flex-1">{file.name}</span>
          <span className="text-slate-400 flex-shrink-0">↗</span>
        </a>
      ))}
    </div>
  )
}

