import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Send, Paperclip, Image, Mic, CheckCheck, Check, Eye } from 'lucide-react'
import { format } from 'date-fns'
import { useChatStore } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import client from '../api/client'
import toast from 'react-hot-toast'

export default function ChatWindow() {
  const { t } = useTranslation()
  const { activeConversation, messages, setMessages } = useChatStore()
  const { user } = useAuthStore()
  const { sendMessage } = useWebSocket()
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const fileRef = useRef(null)

  const convId = activeConversation?.id
  const convMessages = messages[convId] || []

  useEffect(() => {
    if (!convId) return
    setLoading(true)
    const url = activeConversation.isGroup
      ? `/messages/group/${convId}/history`
      : `/messages/conversation/${convId}`
    client.get(url).then((r) => setMessages(convId, r.data)).catch(() => {}).finally(() => setLoading(false))
  }, [convId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [convMessages.length])

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
  }

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
        <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center text-white font-semibold text-sm">
          {activeConversation.name.slice(0, 2).toUpperCase()}
        </div>
        <div>
          <h2 className="font-semibold text-gray-900">{activeConversation.name}</h2>
          <p className="text-xs text-gray-500">{activeConversation.isGroup ? t('chat.groupChat') : t('chat.directMessage')}</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-thin">
        {loading && <p className="text-center text-sm text-gray-400">{t('chat.loading')}</p>}
        {!loading && convMessages.length === 0 && (
          <p className="text-center text-sm text-gray-400 mt-8">{t('chat.noMessages')}</p>
        )}
        {convMessages.map((msg) => (
          <MessageBubble key={msg.message_id} msg={msg} isOwn={msg.sender_id === user?.user_id} />
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="px-4 py-3 border-t border-gray-100 bg-white">
        <div className="flex items-end gap-2">
          <button onClick={() => fileRef.current?.click()} className="p-2 text-gray-400 hover:text-gray-600 transition-colors">
            <Paperclip size={20} />
          </button>
          <input ref={fileRef} type="file" accept="image/*,video/*,audio/*" className="hidden" onChange={handleFileUpload} />
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
      </div>
    </div>
  )
}

function MessageBubble({ msg, isOwn }) {
  const isMedia = msg.media_type !== 'text'
  const ts = msg.timestamp ? format(new Date(msg.timestamp), 'HH:mm') : ''
  const reactions = Object.entries(msg.reactions || {})

  return (
    <div className={`flex ${isOwn ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-xs lg:max-w-md ${isOwn ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
        <div className={`px-4 py-2 rounded-2xl text-sm ${
          isOwn
            ? 'bg-primary text-white rounded-br-sm'
            : 'bg-gray-100 text-gray-900 rounded-bl-sm'
        }`}>
          {isMedia ? (
            <div className="flex items-center gap-2">
              {msg.media_type === 'image' && <Image size={16} />}
              {msg.media_type === 'voice' && <Mic size={16} />}
              <span className="text-xs opacity-80">[{msg.media_type}] {msg.content}</span>
            </div>
          ) : (
            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
          )}
        </div>

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
          {isOwn && <StatusIcon status={msg.delivery_status} />}
        </div>
      </div>
    </div>
  )
}

function StatusIcon({ status }) {
  if (status === 'read') return <Eye size={12} className="text-blue-500" />
  if (status === 'delivered') return <CheckCheck size={12} />
  return <Check size={12} />
}
