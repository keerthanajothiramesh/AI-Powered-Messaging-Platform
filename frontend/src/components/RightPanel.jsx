import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Users, Loader2, Sparkles, Search, Bot, Settings, Mail, Clock, Mic, Video } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import client from '../api/client'
import toast from 'react-hot-toast'
import NotificationsDropdown from './NotificationsDropdown'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function resolveUrl(url) {
  if (!url) return ''
  return url.startsWith('http') ? url : `${API_BASE}${url}`
}

export default function RightPanel({ onSearchOpen, showAI, onAIToggle, onSettingsOpen }) {
  const { t, i18n } = useTranslation()
  const { activeConversation, messages } = useChatStore()

  const [groupTab, setGroupTab] = useState('members')
  const [members, setMembers] = useState([])
  const [summary, setSummary] = useState(null)
  const [summarising, setSummarising] = useState(false)

  const [dmTab, setDmTab] = useState('info')
  const [otherUser, setOtherUser] = useState(null)
  const [userLoading, setUserLoading] = useState(false)

  const convId = activeConversation?.id
  const convMessages = messages[convId] || []
  const sharedMedia = convMessages.filter((m) => m.media_type !== 'text' && !m.deleted)

  useEffect(() => {
    if (!activeConversation?.isGroup) { setMembers([]); return }
    client.get(`/groups/${activeConversation.id}`)
      .then((r) => setMembers(r.data.members || []))
      .catch(() => {})
  }, [activeConversation?.id])

  useEffect(() => {
    if (!activeConversation || activeConversation.isGroup) { setOtherUser(null); return }
    setUserLoading(true)
    client.get(`/users/${activeConversation.id}`)
      .then((r) => setOtherUser(r.data))
      .catch(() => {})
      .finally(() => setUserLoading(false))
  }, [activeConversation?.id])

  const handleSummary = async () => {
    if (!activeConversation?.isGroup) return
    setSummarising(true)
    setSummary(null)
    try {
      const r = await client.post('/ai/summarise', { group_id: activeConversation.id, days: 14 })
      setSummary(r.data.summary)
    } catch { toast.error('Summary failed') } finally { setSummarising(false) }
  }

  return (
    <div className="w-60 flex flex-col bg-white border-l border-gray-100 flex-shrink-0">
      {/* Toolbar — replaces the old floating fixed buttons */}
      <div className="px-2 py-2.5 border-b border-gray-100 flex items-center justify-end gap-0.5">
        <button
          onClick={onSearchOpen}
          className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          title="Search messages"
        >
          <Search size={16} />
        </button>
        <button
          onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en')}
          className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors text-xs font-semibold"
          title="Toggle language"
        >
          {i18n.language === 'en' ? 'JP' : 'EN'}
        </button>
        <NotificationsDropdown />
        <button
          onClick={onAIToggle}
          className={`p-1.5 rounded-lg transition-colors ${showAI ? 'text-primary bg-red-50' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-100'}`}
          title="AI Assistant"
        >
          <Bot size={16} />
        </button>
        <button
          onClick={onSettingsOpen}
          className="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          title="Settings"
        >
          <Settings size={16} />
        </button>
      </div>

      {!activeConversation ? (
        <div className="flex-1 flex items-center justify-center px-4">
          <p className="text-xs text-gray-400 text-center">Select a conversation to see details</p>
        </div>
      ) : activeConversation.isGroup ? (
        <GroupPanel
          members={members}
          groupTab={groupTab}
          setGroupTab={setGroupTab}
          summary={summary}
          summarising={summarising}
          onSummary={handleSummary}
          t={t}
        />
      ) : (
        <DmPanel
          dmTab={dmTab}
          setDmTab={setDmTab}
          otherUser={otherUser}
          userLoading={userLoading}
          sharedMedia={sharedMedia}
        />
      )}
    </div>
  )
}

function GroupPanel({ members, groupTab, setGroupTab, summary, summarising, onSummary, t }) {
  return (
    <>
      <div className="flex border-b border-gray-100 text-xs font-medium">
        <button
          onClick={() => setGroupTab('members')}
          className={`flex-1 py-2 flex items-center justify-center gap-1 transition-colors ${groupTab === 'members' ? 'text-primary border-b-2 border-primary' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <Users size={13} /> Members
        </button>
        <button
          onClick={() => setGroupTab('summary')}
          className={`flex-1 py-2 flex items-center justify-center gap-1 transition-colors ${groupTab === 'summary' ? 'text-primary border-b-2 border-primary' : 'text-gray-500 hover:text-gray-700'}`}
        >
          <Sparkles size={13} /> Summary
        </button>
      </div>

      {groupTab === 'members' ? (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-2 px-4 py-2">
              <div className="relative flex-shrink-0">
                <div className="w-7 h-7 rounded-full bg-gray-300 flex items-center justify-center text-xs text-white font-medium">
                  {m.display_name.slice(0, 2).toUpperCase()}
                </div>
                <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border border-white ${m.user_presence === 'online' ? 'bg-green-500' : 'bg-gray-400'}`} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-medium text-gray-800 truncate">{m.display_name}</p>
                {m.role === 'admin' && <span className="text-xs text-primary">admin</span>}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
          <button
            onClick={onSummary}
            disabled={summarising}
            className="w-full flex items-center justify-center gap-2 py-2 bg-primary/10 text-primary rounded-lg text-sm font-medium hover:bg-primary/20 disabled:opacity-60 transition-colors"
          >
            {summarising ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {t('groups.aiSummary')}
          </button>
          {summary && (
            <div className="mt-2 p-2 bg-gray-50 rounded-lg text-xs text-gray-700 leading-relaxed max-h-60 overflow-y-auto scrollbar-thin">
              {summary}
            </div>
          )}
        </div>
      )}
    </>
  )
}

function DmPanel({ dmTab, setDmTab, otherUser, userLoading, sharedMedia }) {
  return (
    <>
      <div className="flex border-b border-gray-100 text-xs font-medium">
        <button
          onClick={() => setDmTab('info')}
          className={`flex-1 py-2 transition-colors ${dmTab === 'info' ? 'text-primary border-b-2 border-primary' : 'text-gray-500 hover:text-gray-700'}`}
        >
          Info
        </button>
        <button
          onClick={() => setDmTab('shared')}
          className={`flex-1 py-2 transition-colors ${dmTab === 'shared' ? 'text-primary border-b-2 border-primary' : 'text-gray-500 hover:text-gray-700'}`}
        >
          Shared ({sharedMedia.length})
        </button>
      </div>

      {dmTab === 'info' ? (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {userLoading ? (
            <div className="flex items-center justify-center p-6">
              <Loader2 size={20} className="animate-spin text-gray-400" />
            </div>
          ) : otherUser ? (
            <div className="p-4">
              <div className="flex flex-col items-center gap-2 mb-4">
                <div className="w-16 h-16 rounded-full bg-primary flex items-center justify-center text-white text-xl font-semibold">
                  {otherUser.display_name?.slice(0, 2).toUpperCase() || '??'}
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-gray-900">{otherUser.display_name}</p>
                  <p className={`text-xs font-medium mt-0.5 ${otherUser.user_presence === 'online' ? 'text-green-500' : 'text-gray-400'}`}>
                    {otherUser.user_presence === 'online' ? '● Online' : '● Offline'}
                  </p>
                </div>
              </div>

              {otherUser.email && (
                <div className="flex items-start gap-2 py-2.5 border-t border-gray-100">
                  <Mail size={13} className="text-gray-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-gray-600 break-all">{otherUser.email}</p>
                </div>
              )}

              {otherUser.status && (
                <div className="flex items-start gap-2 py-2.5 border-t border-gray-100">
                  <Clock size={13} className="text-gray-400 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-gray-600">{otherUser.status}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-gray-400 text-center mt-6">Unable to load user info</p>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {sharedMedia.length === 0 ? (
            <p className="text-xs text-gray-400 text-center mt-6">No shared media yet</p>
          ) : (
            <div className="grid grid-cols-2 gap-1.5">
              {sharedMedia.map((msg) => (
                <MediaThumb key={msg.message_id} msg={msg} />
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}

function MediaThumb({ msg }) {
  const url = resolveUrl(msg.media_url)

  if (msg.media_type === 'image') {
    return (
      <img
        src={url}
        alt="shared"
        className="w-full aspect-square object-cover rounded-lg cursor-pointer hover:opacity-80 transition-opacity"
        onClick={() => url && window.open(url, '_blank')}
        onError={(e) => { e.currentTarget.style.display = 'none' }}
      />
    )
  }
  if (msg.media_type === 'voice') {
    return (
      <div className="flex flex-col items-center justify-center gap-1 p-2 bg-gray-50 rounded-lg aspect-square">
        <Mic size={18} className="text-gray-400" />
        <span className="text-xs text-gray-400">Voice</span>
      </div>
    )
  }
  if (msg.media_type === 'video') {
    return (
      <div className="flex flex-col items-center justify-center gap-1 p-2 bg-gray-50 rounded-lg aspect-square cursor-pointer hover:bg-gray-100 transition-colors" onClick={() => url && window.open(url, '_blank')}>
        <Video size={18} className="text-gray-400" />
        <span className="text-xs text-gray-400">Video</span>
      </div>
    )
  }
  return null
}
