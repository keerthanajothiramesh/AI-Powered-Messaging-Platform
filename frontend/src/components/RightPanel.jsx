import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Users, Loader2, Sparkles, Search, Bot, Settings, Mail, Clock, Mic, Video, FileText } from 'lucide-react'
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
    <div className="w-60 flex flex-col bg-white border-l border-slate-100 flex-shrink-0 shadow-sm">
      {/* Toolbar */}
      <div className="px-2 py-2.5 border-b border-slate-100 flex items-center justify-end gap-0.5">
        <button
          onClick={onSearchOpen}
          className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
          title="Search messages"
        >
          <Search size={16} />
        </button>
        <button
          onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en')}
          className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all text-xs font-bold"
          title="Toggle language"
        >
          {i18n.language === 'en' ? 'JP' : 'EN'}
        </button>
        <NotificationsDropdown />
        <button
          onClick={onAIToggle}
          className={`p-1.5 rounded-lg transition-all ${
            showAI
              ? 'text-indigo-600 bg-indigo-50'
              : 'text-slate-500 hover:text-indigo-600 hover:bg-indigo-50'
          }`}
          title="AI Assistant"
        >
          <Bot size={16} />
        </button>
        <button
          onClick={onSettingsOpen}
          className="p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
          title="Settings"
        >
          <Settings size={16} />
        </button>
      </div>

      {!activeConversation ? (
        <div className="flex-1 flex items-center justify-center px-4">
          <div className="text-center">
            <div className="w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-3"
                 style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}>
              <Sparkles size={20} className="text-indigo-400" />
            </div>
            <p className="text-xs text-slate-400 text-center leading-relaxed">Select a conversation to see details</p>
          </div>
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
      <div className="flex border-b border-slate-100 text-xs font-medium">
        <button
          onClick={() => setGroupTab('members')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1 transition-all ${
            groupTab === 'members' ? 'text-indigo-600 border-b-2 border-indigo-500' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Users size={13} /> Members
        </button>
        <button
          onClick={() => setGroupTab('summary')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1 transition-all ${
            groupTab === 'summary' ? 'text-indigo-600 border-b-2 border-indigo-500' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Sparkles size={13} /> Summary
        </button>
      </div>

      {groupTab === 'members' ? (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {members.map((m) => (
            <div key={m.user_id} className="flex items-center gap-2.5 px-4 py-2.5 hover:bg-indigo-50/40 transition-all">
              <div className="relative flex-shrink-0">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-xs text-white font-semibold"
                  style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
                >
                  {m.display_name.slice(0, 2).toUpperCase()}
                </div>
                <span className={`absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full border-2 border-white ${
                  m.user_presence === 'online' ? 'bg-emerald-400' : 'bg-slate-300'
                }`} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-800 truncate">{m.display_name}</p>
                {m.role === 'admin' && (
                  <span className="text-xs font-medium" style={{ color: '#6366f1' }}>admin</span>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-3 scrollbar-thin">
          <button
            onClick={onSummary}
            disabled={summarising}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-60"
            style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)', color: '#6366f1' }}
          >
            {summarising ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {t('groups.aiSummary')}
          </button>
          {summary && (
            <div className="mt-3 p-3 rounded-xl text-xs text-slate-700 leading-relaxed max-h-60 overflow-y-auto scrollbar-thin border border-indigo-100"
                 style={{ background: 'linear-gradient(135deg, #f0f4ff, #f5f3ff)' }}>
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
      <div className="flex border-b border-slate-100 text-xs font-medium">
        <button
          onClick={() => setDmTab('info')}
          className={`flex-1 py-2.5 transition-all ${
            dmTab === 'info' ? 'text-indigo-600 border-b-2 border-indigo-500' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Info
        </button>
        <button
          onClick={() => setDmTab('shared')}
          className={`flex-1 py-2.5 transition-all ${
            dmTab === 'shared' ? 'text-indigo-600 border-b-2 border-indigo-500' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Shared ({sharedMedia.length})
        </button>
      </div>

      {dmTab === 'info' ? (
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {userLoading ? (
            <div className="flex items-center justify-center p-6">
              <Loader2 size={20} className="animate-spin text-indigo-400" />
            </div>
          ) : otherUser ? (
            <div className="p-4">
              <div className="flex flex-col items-center gap-2.5 mb-5">
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-xl font-bold shadow-lg"
                  style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
                >
                  {otherUser.display_name?.slice(0, 2).toUpperCase() || '??'}
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-slate-900">{otherUser.display_name}</p>
                  <p className={`text-xs font-medium mt-0.5 ${
                    otherUser.user_presence === 'online' ? 'text-emerald-500' : 'text-slate-400'
                  }`}>
                    {otherUser.user_presence === 'online' ? '● Online' : '● Offline'}
                  </p>
                </div>
              </div>

              {otherUser.email && (
                <div className="flex items-start gap-2 py-2.5 border-t border-slate-100">
                  <Mail size={13} className="text-indigo-300 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-600 break-all">{otherUser.email}</p>
                </div>
              )}

              {otherUser.status && (
                <div className="flex items-start gap-2 py-2.5 border-t border-slate-100">
                  <Clock size={13} className="text-indigo-300 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-slate-600">{otherUser.status}</p>
                </div>
              )}
            </div>
          ) : (
            <p className="text-xs text-slate-400 text-center mt-6">Unable to load user info</p>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {sharedMedia.length === 0 ? (
            <p className="text-xs text-slate-400 text-center mt-6">No shared media yet</p>
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
        className="w-full aspect-square object-cover rounded-xl cursor-pointer hover:opacity-80 transition-opacity shadow-sm"
        onClick={() => url && window.open(url, '_blank')}
        onError={(e) => { e.currentTarget.style.display = 'none' }}
      />
    )
  }
  if (msg.media_type === 'voice') {
    return (
      <div className="flex flex-col items-center justify-center gap-1 p-2 rounded-xl aspect-square border border-indigo-100"
           style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}>
        <Mic size={18} className="text-indigo-400" />
        <span className="text-xs text-indigo-400 font-medium">Voice</span>
      </div>
    )
  }
  if (msg.media_type === 'video') {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1 p-2 rounded-xl aspect-square cursor-pointer hover:opacity-80 transition-all border border-indigo-100"
        style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}
        onClick={() => url && window.open(url, '_blank')}
      >
        <Video size={18} className="text-indigo-400" />
        <span className="text-xs text-indigo-400 font-medium">Video</span>
      </div>
    )
  }
  if (msg.media_type === 'document' || msg.media_type === 'file') {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1 p-2 rounded-xl aspect-square cursor-pointer hover:opacity-80 transition-all border border-violet-100"
        style={{ background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)' }}
        onClick={() => url && window.open(url, '_blank')}
      >
        <FileText size={18} className="text-violet-400" />
        <span className="text-xs text-violet-400 font-medium">Doc</span>
      </div>
    )
  }
  return null
}
