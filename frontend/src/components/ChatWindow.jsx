import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Paperclip, Image, Mic, MicOff, CheckCheck, Check, Eye, Pencil, Trash2, Square } from 'lucide-react'
import { format, isToday, isYesterday } from 'date-fns'
import { useChatStore } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
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
  const d = new Date(lastSeenTs)
  if (isToday(d)) return { text: `Last seen at ${format(d, 'HH:mm')}`, green: false }
  if (isYesterday(d)) return { text: 'Last seen yesterday', green: false }
  return { text: `Last seen ${format(d, 'dd MMM')}`, green: false }
}

export default function ChatWindow() {
  const { t } = useTranslation()
  const { activeConversation, messages, setMessages, onlineUsers, lastSeen } = useChatStore()
  const { user } = useAuthStore()
  const { sendMessage } = useWebSocket()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [recording, setRecording] = useState(false)
  const [recordingSeconds, setRecordingSeconds] = useState(0)
  const bottomRef = useRef(null)
  const fileRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const timerRef = useRef(null)

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
        // Mark all unread incoming messages as read
        const unread = r.data.filter(
          (m) => m.sender_id !== user?.user_id && m.delivery_status !== 'read'
        )
        unread.forEach((m) => client.put(`/messages/${m.message_id}/read`).catch(() => {}))
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [convId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [convMessages.length])

  useEffect(() => {
    return () => {
      clearInterval(timerRef.current)
      mediaRecorderRef.current?.stream?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const handleSend = () => {
    const text = input.trim()
    if (!text || !convId) return
    sendMessage(text, convId, activeConversation.isGroup)
    setInput('')
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
      sendMessage(`[Media: ${file.name}]`, convId, activeConversation.isGroup, r.data.media_type, r.data.url)
      toast.success('File uploaded!')
    } catch { toast.error('Upload failed') }
    e.target.value = ''
  }

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data)
      }

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
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
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
      <div className="flex-1 flex items-center justify-center bg-gray-50">
        <div className="text-center text-gray-400">
          <div className="w-16 h-16 bg-gray-200 rounded-full flex items-center justify-center mx-auto mb-4">
            <Send size={24} />
          </div>
          <p className="font-medium">Select a conversation</p>
          <p className="text-sm">Choose from the list or search for a user</p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 flex flex-col bg-white">
      <div className="px-6 py-4 border-b border-gray-100 flex items-center gap-3 bg-white shadow-sm">
        <div className="relative flex-shrink-0">
          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-white font-semibold text-sm">
            {activeConversation.name.slice(0, 2).toUpperCase()}
          </div>
          {!activeConversation.isGroup && (
            <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white transition-colors ${onlineUsers.has(activeConversation.id) ? 'bg-green-500' : 'bg-gray-300'}`} />
          )}
        </div>
        <div>
          <h2 className="font-semibold text-gray-900">{activeConversation.name}</h2>
          {activeConversation.isGroup ? (
            <p className="text-xs text-gray-500">{t('chat.groupChat')}</p>
          ) : (() => {
            const { text, green } = formatPresence(
              onlineUsers.has(activeConversation.id),
              lastSeen[activeConversation.id]
            )
            return <p className={`text-xs font-medium ${green ? 'text-green-500' : 'text-gray-400'}`}>{text}</p>
          })()}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin">
        {loading && <p className="text-center text-sm text-gray-400">{t('chat.loading')}</p>}
        {!loading && convMessages.length === 0 && (
          <p className="text-center text-sm text-gray-400 mt-8">{t('chat.noMessages')}</p>
        )}
        {convMessages.map((msg) => (
          <MessageBubble
            key={msg.message_id}
            msg={msg}
            isOwn={msg.sender_id === user?.user_id}
            onEdit={handleEdit}
            onDelete={handleDelete}
          />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 py-3 border-t border-gray-100 bg-white">
        {recording ? (
          <div className="flex items-center gap-3 px-4 py-2 bg-red-50 rounded-xl border border-red-200">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <Mic size={18} className="text-red-500" />
            <span className="text-sm text-red-600 font-medium flex-1">
              Recording… {formatRecordingTime(recordingSeconds)}
            </span>
            <button
              onClick={stopRecording}
              className="flex items-center gap-1 px-3 py-1 bg-red-500 text-white rounded-lg text-xs font-medium hover:bg-red-600 transition-colors"
            >
              <Square size={12} /> Stop
            </button>
          </div>
        ) : (
          <div className="flex items-end gap-2">
            <button onClick={() => fileRef.current?.click()} className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
              <Paperclip size={20} />
            </button>
            <input ref={fileRef} type="file" accept="image/*,video/*" className="hidden" onChange={handleFileUpload} />
            <button onClick={startRecording} className="p-2 text-gray-400 hover:text-red-500 transition-colors" title="Record voice message">
              <Mic size={20} />
            </button>
            <div className="flex-1 relative">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={t('chat.typeMessage')}
                rows={1}
                className="w-full px-4 py-2 bg-gray-50 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-primary/20 text-sm max-h-32"
                style={{ minHeight: '40px' }}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="p-2 bg-primary text-white rounded-xl hover:bg-primary-dark transition-colors disabled:opacity-40"
            >
              <Send size={18} />
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

function MessageBubble({ msg, isOwn, onEdit, onDelete }) {
  const [hovered, setHovered] = useState(false)
  const [editing, setEditing] = useState(false)
  const [editText, setEditText] = useState(msg.content)

  const isDeleted = msg.deleted
  const isVoice = msg.media_type === 'voice'
  const isImage = msg.media_type === 'image'
  const isVideo = msg.media_type === 'video'
  const isMedia = msg.media_type !== 'text'
  const ts = msg.timestamp ? format(new Date(msg.timestamp), 'HH:mm') : ''
  const reactions = Object.entries(msg.reactions || {})

  const handleEditSubmit = () => {
    const trimmed = editText.trim()
    if (trimmed && trimmed !== msg.content) {
      onEdit(msg.message_id, trimmed)
    }
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
        {isOwn && !isDeleted && !editing && hovered && (
          <div className="flex gap-1 justify-end">
            {!isMedia && (
              <button
                onClick={() => { setEditText(msg.content); setEditing(true) }}
                className="p-1 rounded text-gray-400 hover:text-blue-500 hover:bg-gray-100 transition-colors"
                title="Edit"
              >
                <Pencil size={12} />
              </button>
            )}
            <button
              onClick={() => onDelete(msg.message_id)}
              className="p-1 rounded text-gray-400 hover:text-red-500 hover:bg-gray-100 transition-colors"
              title="Delete"
            >
              <Trash2 size={12} />
            </button>
          </div>
        )}

        <div className={`px-4 py-2 rounded-2xl text-sm ${
          isOwn
            ? 'bg-primary text-white rounded-br-sm'
            : 'bg-gray-100 text-gray-900 rounded-bl-sm'
        } ${isDeleted ? 'opacity-50' : ''}`}>
          {editing ? (
            <div className="flex flex-col gap-2" style={{ minWidth: '180px' }}>
              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                onKeyDown={handleEditKeyDown}
                rows={2}
                autoFocus
                className="bg-white/20 rounded px-2 py-1 text-sm resize-none focus:outline-none w-full"
              />
              <div className="flex gap-2 justify-end text-xs">
                <button onClick={() => setEditing(false)} className="px-2 py-0.5 rounded bg-white/20 hover:bg-white/30">Cancel</button>
                <button onClick={handleEditSubmit} className="px-2 py-0.5 rounded bg-white/30 hover:bg-white/40 font-medium">Save</button>
              </div>
            </div>
          ) : isDeleted ? (
            <p className="italic opacity-60">{msg.content}</p>
          ) : isVoice ? (
            <div className="flex flex-col gap-1">
              <div className="flex items-center gap-2 text-xs opacity-80 mb-1">
                <Mic size={13} /> Voice message
              </div>
              {msg.media_url
                ? <audio controls src={resolveMediaUrl(msg.media_url)} style={{ height: '36px', minWidth: '220px' }} />
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
                    className="rounded-lg max-w-xs max-h-56 object-cover cursor-pointer hover:opacity-90 transition-opacity"
                    onClick={() => window.open(resolveMediaUrl(msg.media_url), '_blank')}
                    onError={(e) => { e.target.style.display = 'none' }}
                  />
                )
                : <div className="flex items-center gap-2 text-xs opacity-80"><Image size={14} /> Image unavailable</div>
              }
            </div>
          ) : isVideo ? (
            <div className="flex flex-col gap-1">
              {msg.media_url
                ? (
                  <video
                    controls
                    src={resolveMediaUrl(msg.media_url)}
                    className="rounded-lg max-w-xs max-h-56"
                    preload="metadata"
                  />
                )
                : <span className="text-xs opacity-70">Video unavailable</span>
              }
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
          )}
        </div>

        {msg.edited && !isDeleted && (
          <span className="text-xs text-gray-400 italic">edited</span>
        )}

        {reactions.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {reactions.map(([emoji, users]) => (
              <span key={emoji} className="text-xs bg-white border border-gray-200 rounded-full px-2 py-0.5 shadow-sm">
                {emoji} {users.length}
              </span>
            ))}
          </div>
        )}

        <div className="flex items-center gap-1 text-xs text-gray-400">
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
    read:      { icon: <CheckCheck size={14} />, color: 'text-blue-500', label: 'Read' },
    delivered: { icon: <CheckCheck size={14} />, color: 'text-gray-400', label: 'Delivered' },
    sent:      { icon: <Check size={14} />,      color: 'text-gray-400', label: 'Sent' },
    queued:    { icon: <Check size={14} />,      color: 'text-gray-300', label: 'Queued' },
    failed:    { icon: <Check size={14} />,      color: 'text-red-400',  label: 'Failed' },
  }
  const cfg = configs[status] || configs.sent
  const timeLabel = timestamp
    ? `${cfg.label} · ${format(new Date(timestamp), 'HH:mm')}`
    : cfg.label

  return (
    <span className="relative group/status inline-flex cursor-default">
      <span className={cfg.color}>{cfg.icon}</span>
      <span className="absolute bottom-full right-0 mb-1.5 px-2 py-0.5 text-xs bg-gray-800 text-white rounded whitespace-nowrap opacity-0 group-hover/status:opacity-100 transition-opacity pointer-events-none z-10">
        {timeLabel}
      </span>
    </span>
  )
}
