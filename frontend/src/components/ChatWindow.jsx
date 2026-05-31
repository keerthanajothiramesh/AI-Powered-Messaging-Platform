import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Paperclip, Image, Mic, CheckCheck, Check, Pencil, Trash2, Square, FileText, MessageCircle, Info, Image as ImageIcon, ImagePlus, FolderOpen, Music } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import { formatIST, formatISTFull, isISTToday, isISTYesterday } from '../utils/time'
import client from '../api/client'
import toast from 'react-hot-toast'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function resolveMediaUrl(url) {
  if (!url) return ''
  if (url.startsWith('http')) return url
  return `${API_BASE}${url}`
}

function formatPresence(isOnline, lastSeenTs) {
  if (isOnline) return { text: 'Online', green: true }
  if (!lastSeenTs) return { text: 'Offline', green: false }
  if (isISTToday(lastSeenTs)) return { text: `Last seen at ${formatIST(lastSeenTs)}`, green: false }
  if (isISTYesterday(lastSeenTs)) return { text: 'Last seen yesterday', green: false }
  return { text: `Last seen ${formatIST(lastSeenTs, 'dd MMM')}`, green: false }
}

export default function ChatWindow({ onRightTabChange, activeRightTab, onInfoOpen, onSharedOpen }) {
  const { t } = useTranslation()
  const { activeConversation, messages, setMessages, onlineUsers, lastSeen, typingUsers, setReaction } = useChatStore()
  const { user } = useAuthStore()
  const { sendMessage, sendTyping } = useWebSocket()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [recording, setRecording] = useState(false)
  const [suggestions, setSuggestions] = useState([])
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const [showAttachMenu, setShowAttachMenu] = useState(false)
  const bottomRef = useRef(null)
  const fileRef = useRef(null)
  const attachMenuRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const timerRef = useRef(null)
  const lastTypingSentRef = useRef(0)

  const convId = activeConversation?.id
  const convMessages = messages[convId] || []

  useEffect(() => {
    if (!convId) return
    setLoading(true)
    const url = activeConversation.isGroup
      ? `/messages/group/${convId}/history`
      : `/messages/conversation/${convId}`
    client.get(url)
      .then((r) => {
        setMessages(convId, r.data)
        const unread = r.data.filter((m) => m.sender_id !== user?.user_id && m.delivery_status !== 'read')
        unread.forEach((m) => client.put(`/messages/${m.message_id}/read`).catch(() => {}))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [convId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [convMessages.length])

  useEffect(() => {
    if (!convId || convMessages.length === 0) { setSuggestions([]); return }
    const last = convMessages[convMessages.length - 1]
    if (last.sender_id === user?.user_id) { setSuggestions([]); return }
    if (last.media_type !== 'text' || last.deleted) { setSuggestions([]); return }
    const context = convMessages.slice(-5, -1).map((m) => m.content)
    client.post('/messages/suggest-replies', { message: last.content, context })
      .then((r) => setSuggestions(r.data.suggestions || []))
      .catch(() => setSuggestions([]))
  }, [convMessages.length, convId])

  useEffect(() => {
    return () => {
      clearInterval(timerRef.current)
      mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  useEffect(() => {
    if (!showAttachMenu) return
    const handler = (e) => {
      if (attachMenuRef.current && !attachMenuRef.current.contains(e.target)) setShowAttachMenu(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [showAttachMenu])

  const handleAttachOption = (accept) => {
    setShowAttachMenu(false)
    fileRef.current.accept = accept
    fileRef.current.click()
  }

  const handleReact = async (messageId, emoji) => {
    try {
      const currentMsg = (useChatStore.getState().messages[convId] || []).find((m) => m.message_id === messageId)
      if (currentMsg) {
        const updated = { ...(currentMsg.reactions || {}) }
        if (!updated[emoji]) updated[emoji] = []
        if (!updated[emoji].includes(user?.user_id)) updated[emoji] = [...updated[emoji], user?.user_id]
        setReaction(convId, messageId, updated)
      }
      await client.post(`/messages/${messageId}/react?emoji=${encodeURIComponent(emoji)}`)
    } catch { /* silent */ }
  }

  const handleSend = () => {
    const text = input.trim()
    if (!text || !convId) return
    sendMessage(text, convId, activeConversation.isGroup)
    setInput('')
    setSuggestions([])
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend() }
  }

  const handleFileUpload = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    if (activeConversation.isGroup) fd.append('group_id', convId)
    try {
      const r = await client.post('/media/upload', fd)
      sendMessage(file.name, convId, activeConversation.isGroup, r.data.media_type, r.data.url)
      if (r.data.storage === 's3') toast.success('Uploaded to S3')
      else toast.success('File sent')
    } catch { toast.error('Upload failed') }
    e.target.value = ''
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' })
        clearInterval(timerRef.current)
        setRecordingSeconds(0)
        await uploadVoice(blob)
      }

      recorder.start()
      setRecording(true)
      setRecordingSeconds(0)
      timerRef.current = setInterval(() => setRecordingSeconds((s) => s + 1), 1000)
    } catch {
      toast.error('Microphone access denied')
    }
  }

  const stopRecording = () => {
    if (mediaRecorderRef.current?.state === 'recording') mediaRecorderRef.current.stop()
    setRecording(false)
  }

  const uploadVoice = async (blob) => {
    const fd = new FormData()
    fd.append('file', blob, 'voice-message.webm')
    if (activeConversation?.isGroup) fd.append('group_id', convId)
    try {
      const r = await client.post('/media/upload', fd)
      sendMessage('🎤 Voice message', convId, activeConversation.isGroup, 'voice', r.data.url)
      toast.success('Voice message sent!')
    } catch {
      toast.error('Failed to send voice message')
    }
  }

  const handleEdit = async (messageId, newContent) => {
    try {
      await client.put(`/messages/${messageId}`, { content: newContent })
    } catch {
      toast.error('Failed to edit message')
    }
  }

  const handleDelete = async (messageId) => {
    try {
      await client.delete(`/messages/${messageId}`)
    } catch {
      toast.error('Failed to delete message')
    }
  }

  const formatRecordingTime = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  if (!activeConversation) {
    return (
      <div className="flex-1 flex items-center justify-center"
           style={{ background: 'linear-gradient(135deg, #eef2ff 0%, #f8faff 50%, #f5f3ff 100%)' }}>
        <div className="text-center px-6">
          <div
            className="w-24 h-24 rounded-3xl flex items-center justify-center mx-auto mb-5 shadow-xl"
            style={{ background: 'linear-gradient(135deg, #c7d2fe, #ddd6fe)' }}
          >
            <MessageCircle size={38} className="text-indigo-500" />
          </div>
          <p className="font-bold text-slate-600 text-xl">Select a conversation</p>
          <p className="text-sm mt-2 text-slate-400">Choose from the list or search for a user</p>
        </div>
      </div>
    )
  }

  // Group header chips control the right panel tab; DM chips open modals
  const groupTabs = [
    { key: 'members', label: 'Members' },
    { key: 'summary', label: 'Summary' },
    { key: 'ai', label: 'AI' },
  ]

  return (
    <div className="flex-1 flex flex-col bg-white overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3 bg-white shadow-sm flex-shrink-0">
        <div className="relative flex-shrink-0">
          <div
            className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold text-sm shadow-md"
            style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
          >
            {activeConversation.name.slice(0, 2).toUpperCase()}
          </div>
          {!activeConversation.isGroup && (
            <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white transition-colors ${
              onlineUsers.has(activeConversation.id) ? 'bg-emerald-400' : 'bg-slate-300'
            }`} />
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="font-bold text-slate-800">{activeConversation.name}</h2>
            <div className="flex gap-1">
              {activeConversation.isGroup
                ? groupTabs.map((tab) => (
                    <button
                      key={tab.key}
                      onClick={() => onRightTabChange?.(activeRightTab === tab.key ? null : tab.key)}
                      className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border transition-all ${
                        activeRightTab === tab.key
                          ? 'text-white border-transparent'
                          : 'text-slate-500 border-slate-200 hover:border-violet-300 hover:text-violet-600 bg-white'
                      }`}
                      style={activeRightTab === tab.key ? { background: 'linear-gradient(135deg, #818cf8, #7c3aed)', border: 'none' } : {}}
                    >
                      {tab.label}
                    </button>
                  ))
                : (
                  <>
                    <button
                      onClick={() => onInfoOpen?.(activeConversation.id)}
                      className="text-xs px-2.5 py-0.5 rounded-full font-semibold border text-slate-500 border-slate-200 hover:border-violet-300 hover:text-violet-600 bg-white transition-all"
                    >
                      Info
                    </button>
                    <button
                      onClick={() => onSharedOpen?.()}
                      className="text-xs px-2.5 py-0.5 rounded-full font-semibold border text-slate-500 border-slate-200 hover:border-violet-300 hover:text-violet-600 bg-white transition-all"
                    >
                      Shared
                    </button>
                  </>
                )
              }
            </div>
          </div>
          {activeConversation.isGroup ? (
            <p className="text-xs text-slate-400">{t('chat.groupChat')}</p>
          ) : (() => {
            const { text, green } = formatPresence(onlineUsers.has(activeConversation.id), lastSeen[activeConversation.id])
            return <p className={`text-xs font-semibold ${green ? 'text-emerald-500' : 'text-slate-400'}`}>{text}</p>
          })()}
        </div>
      </div>

      {/* Messages area */}
      <div
        className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin"
        style={{ background: 'linear-gradient(to bottom, rgba(238,242,255,0.4), rgba(248,250,252,0.6))' }}
      >
        {loading && <p className="text-center text-sm text-slate-400 mt-4">{t('chat.loading')}</p>}
        {!loading && convMessages.length === 0 && (
          <p className="text-center text-sm text-slate-400 mt-8">{t('chat.noMessages')}</p>
        )}
        {convMessages.map((msg) => (
          <MessageBubble
            key={msg.message_id}
            msg={msg}
            isOwn={msg.sender_id === user?.user_id}
            onEdit={handleEdit}
            onDelete={handleDelete}
            onReact={handleReact}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Reply suggestions */}
      {suggestions.length > 0 && !input && (
        <div className="px-4 pb-2 flex gap-2 flex-wrap flex-shrink-0">
          {suggestions.map((s, i) => (
            <button
              key={i}
              onClick={() => { setInput(s); setSuggestions([]) }}
              className="px-3 py-1.5 text-indigo-600 border border-indigo-200 rounded-full text-xs font-semibold transition-all shadow-sm hover:shadow-md"
              style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {/* Typing indicator */}
      {typingUsers[convId] && (
        <div className="px-6 pb-1 flex items-center gap-2 text-xs text-slate-400 flex-shrink-0">
          <span className="flex gap-0.5 items-center">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400 animate-bounce" style={{ animationDelay: '300ms' }} />
          </span>
          typing…
        </div>
      )}

      {/* Input area */}
      <div className="px-4 py-3 border-t border-slate-100 bg-white flex-shrink-0">
        {recording ? (
          <div className="flex items-center gap-3 px-4 py-2.5 rounded-2xl border border-indigo-200"
               style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}>
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <Mic size={18} className="text-indigo-600" />
            <span className="text-sm text-indigo-700 font-semibold flex-1">
              Recording… {formatRecordingTime(recordingSeconds)}
            </span>
            <button
              onClick={stopRecording}
              className="flex items-center gap-1 px-3 py-1 bg-red-500 text-white rounded-xl text-xs font-semibold hover:bg-red-600 transition-all shadow-sm"
            >
              <Square size={12} /> Stop
            </button>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            {/* Attachment button with dropdown */}
            <div className="relative flex-shrink-0" ref={attachMenuRef}>
              <button
                onClick={() => setShowAttachMenu((p) => !p)}
                className={`p-2 rounded-xl transition-all ${showAttachMenu ? 'text-indigo-600 bg-indigo-50' : 'text-slate-400 hover:text-indigo-600 hover:bg-indigo-50'}`}
                title="Attach file"
              >
                <Paperclip size={20} />
              </button>
              {showAttachMenu && (
                <div className="absolute bottom-full left-0 mb-2 bg-white rounded-2xl shadow-xl border border-slate-100 overflow-hidden z-20 w-44">
                  <p className="px-3 pt-2.5 pb-1 text-xs font-bold text-slate-400 uppercase tracking-wider">Attach</p>
                  <button
                    onClick={() => handleAttachOption('image/*,video/*')}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-violet-50 text-left transition-all"
                  >
                    <div className="w-7 h-7 rounded-lg bg-violet-100 flex items-center justify-center flex-shrink-0">
                      <ImagePlus size={14} className="text-violet-600" />
                    </div>
                    <span className="text-sm text-slate-700 font-medium">Photo & Video</span>
                  </button>
                  <button
                    onClick={() => handleAttachOption('.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.csv')}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-indigo-50 text-left transition-all"
                  >
                    <div className="w-7 h-7 rounded-lg bg-indigo-100 flex items-center justify-center flex-shrink-0">
                      <FolderOpen size={14} className="text-indigo-600" />
                    </div>
                    <span className="text-sm text-slate-700 font-medium">Document</span>
                  </button>
                  <button
                    onClick={() => handleAttachOption('audio/*')}
                    className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-sky-50 text-left transition-all mb-1"
                  >
                    <div className="w-7 h-7 rounded-lg bg-sky-100 flex items-center justify-center flex-shrink-0">
                      <Music size={14} className="text-sky-600" />
                    </div>
                    <span className="text-sm text-slate-700 font-medium">Audio file</span>
                  </button>
                </div>
              )}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.csv"
              className="hidden"
              onChange={handleFileUpload}
            />
            <button
              onClick={startRecording}
              className="p-2 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-xl transition-all flex-shrink-0"
              title="Record voice message"
            >
              <Mic size={20} />
            </button>
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => {
                  setInput(e.target.value)
                  const now = Date.now()
                  if (convId && now - lastTypingSentRef.current > 2000) {
                    sendTyping(convId, activeConversation.isGroup)
                    lastTypingSentRef.current = now
                  }
                }}
                onKeyDown={handleKeyDown}
                placeholder={t('chat.typeMessage')}
                rows={1}
                className="w-full px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-2xl resize-none focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 text-sm max-h-32 transition-all"
                style={{ minHeight: '42px' }}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2.5 text-white rounded-2xl disabled:opacity-40 transition-all shadow-md flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
            >
              <Send size={18} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

const QUICK_REACTIONS = ['👍', '❤️', '😂', '😮', '😢', '🙏']

function MessageBubble({ msg, isOwn, onEdit, onDelete, onReact }) {
  const [hovered, setHovered] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(msg.content)

  const isDeleted = msg.deleted
  const isVoice = msg.media_type === 'voice'
  const isImage = msg.media_type === 'image'
  const isVideo = msg.media_type === 'video'
  const isDocument = msg.media_type === 'document' || msg.media_type === 'file'
  const isMedia = msg.media_type !== 'text'
  const ts = formatIST(msg.timestamp)
  const reactions = Object.entries(msg.reactions || {})

  const handleEditSubmit = () => {
    const trimmed = editText.trim()
    if (trimmed && trimmed !== msg.content) onEdit(msg.message_id, trimmed)
    setEditing(false)
  }

  const handleEditKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleEditSubmit() }
    if (e.key === 'Escape') setEditing(false)
  }

  return (
    <div
      className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className={`max-w-xs lg:max-w-md ${isOwn ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        {!isDeleted && hovered && (
          <div className={`flex gap-0.5 ${isOwn ? 'justify-end' : 'justify-start'}`}>
            {QUICK_REACTIONS.map((emoji) => (
              <button
                key={emoji}
                onClick={(e) => { e.stopPropagation(); onReact(msg.message_id, emoji) }}
                className="text-base hover:scale-125 transition-transform leading-none px-0.5"
                title={emoji}
              >
                {emoji}
              </button>
            ))}
            {isOwn && !editing && (
              <>
                {!isMedia && (
                  <button
                    onClick={() => { setEditText(msg.content); setEditing(true) }}
                    className="ml-1 p-1 rounded-lg text-slate-400 hover:text-blue-500 hover:bg-slate-100 transition-all"
                    title="Edit"
                  >
                    <Pencil size={12} />
                  </button>
                )}
                <button
                  onClick={() => onDelete(msg.message_id)}
                  className="p-1 rounded-lg text-slate-400 hover:text-red-500 hover:bg-slate-100 transition-all"
                  title="Delete"
                >
                  <Trash2 size={12} />
                </button>
              </>
            )}
          </div>
        )}

        <div
          className={`px-4 py-2.5 rounded-2xl text-sm ${
            isOwn
              ? 'text-white rounded-br-sm shadow-md'
              : 'bg-white text-slate-800 rounded-bl-sm shadow-sm border border-slate-100'
          } ${isDeleted ? 'opacity-50' : ''}`}
          style={isOwn ? { background: 'linear-gradient(135deg, #6366f1, #7c3aed)' } : {}}
        >
          {editing ? (
            <div className="flex flex-col gap-2" style={{ minWidth: '180px' }}>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={handleEditKeyDown}
                rows={2}
                autoFocus
                className="bg-white/20 rounded-lg px-2 py-1 text-sm resize-none focus:outline-none w-full placeholder:text-white/50"
              />
              <div className="flex gap-2 justify-end text-xs">
                <button onClick={() => setEditing(false)} className="px-2 py-0.5 rounded-lg bg-white/20 hover:bg-white/30 transition-all">Cancel</button>
                <button onClick={handleEditSubmit} className="px-2 py-0.5 rounded-lg bg-white/30 hover:bg-white/40 font-semibold transition-all">Save</button>
              </div>
            </div>
          ) : isDeleted ? (
            <p className="italic opacity-50">{msg.content}</p>
          ) : isVoice ? (
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-1.5 text-xs opacity-80 mb-1">
                <Mic size={12} /> Voice message
              </div>
              {msg.media_url
                ? <audio controls src={resolveMediaUrl(msg.media_url)} style={{ height: '36px', minWidth: '200px' }} />
                : <span className="text-xs opacity-70">Audio unavailable</span>
              }
            </div>
          ) : isImage ? (
            <div className="flex flex-col gap-1">
              {msg.media_url
                ? (
                  <img
                    src={resolveMediaUrl(msg.media_url)}
                    alt="image"
                    className="rounded-xl max-w-xs max-h-56 object-cover cursor-pointer hover:opacity-90 transition-opacity shadow-sm"
                    onClick={() => window.open(resolveMediaUrl(msg.media_url), '_blank')}
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                )
                : <div className="flex items-center gap-2 text-xs opacity-80"><ImageIcon size={14} /> Image unavailable</div>
              }
            </div>
          ) : isVideo ? (
            <div className="flex flex-col gap-1">
              {msg.media_url
                ? (
                  <video
                    controls
                    src={resolveMediaUrl(msg.media_url)}
                    className="rounded-xl max-w-xs max-h-56"
                    preload="metadata"
                  />
                )
                : <span className="text-xs opacity-70">Video unavailable</span>
              }
            </div>
          ) : isDocument ? (
            <div
              className="flex items-center gap-2.5 p-2 rounded-xl cursor-pointer hover:opacity-80 transition-opacity"
              style={{ minWidth: '190px' }}
              onClick={() => msg.media_url && window.open(resolveMediaUrl(msg.media_url), '_blank')}
            >
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0 ${isOwn ? 'bg-white/20' : 'bg-indigo-100'}`}>
                <FileText size={18} className={isOwn ? 'text-white' : 'text-indigo-600'} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold truncate">{msg.content}</p>
                <p className="text-xs opacity-60 mt-0.5">Click to open</p>
              </div>
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words leading-relaxed">{msg.content}</p>
          )}
        </div>

        {msg.edited && !isDeleted && (
          <span className="text-xs text-slate-400 italic">edited</span>
        )}

        {reactions.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {reactions.map(([emoji, users]) => (
              <span key={emoji} className="text-xs bg-white border border-indigo-100 rounded-full px-2 py-0.5 shadow-sm">
                {emoji} {users.length}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1 text-xs text-slate-400">
          <span>{ts}</span>
          {isOwn && !isDeleted && (
            <StatusIcon
              status={msg.delivery_status}
              timestamp={msg.read_at || msg.delivered_at || msg.timestamp}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function StatusIcon({ status, timestamp }) {
  const configs = {
    read:      { icon: <CheckCheck size={15} />, color: 'text-sky-500',   label: 'Read' },
    delivered: { icon: <CheckCheck size={15} />, color: 'text-slate-400', label: 'Delivered' },
    sent:      { icon: <Check size={14} />,      color: 'text-slate-400', label: 'Sent' },
    queued:    { icon: <Check size={14} />,      color: 'text-slate-300', label: 'Queued' },
    failed:    { icon: <Check size={14} />,      color: 'text-red-400',   label: 'Failed' },
  }
  const cfg = configs[status] || configs.sent
  const timeLabel = timestamp ? `${cfg.label} · ${formatIST(timestamp)}` : cfg.label

  return (
    <span className="relative group/status inline-flex cursor-default">
      <span className={cfg.color}>{cfg.icon}</span>
      <span className="absolute bottom-full right-0 mb-1.5 px-2 py-0.5 text-xs bg-slate-800 text-white rounded-lg whitespace-nowrap opacity-0 group-hover/status:opacity-100 transition-opacity pointer-events-none z-10">
        {timeLabel}
      </span>
    </span>
  )
}
