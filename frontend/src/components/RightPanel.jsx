import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Users, Loader2, Sparkles, Search, Bot, Settings,
  Mic, Video, FileText, Pencil, Trash2, Shield, ShieldOff,
  UserMinus, UserPlus, Check, X, Send, Paperclip, MessageSquare, Plus,
  Image, CheckSquare, Square, ExternalLink, Star,
} from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
import toast from 'react-hot-toast'
import NotificationsDropdown from './NotificationsDropdown'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function resolveUrl(url) {
  if (!url) return ''
  return url.startsWith('http') ? url : `${API_BASE}${url}`
}

export default function RightPanel({ onSearchOpen, onSettingsOpen, activeTab, onTabChange }) {
  const { t, i18n } = useTranslation()
  const { activeConversation } = useChatStore()
  const { user: currentUser } = useAuthStore()

  const [members, setMembers] = useState([])
  const [summary, setSummary] = useState(null)
  const [actionItems, setActionItems] = useState([])
  const [checkedItems, setCheckedItems] = useState({})
  const [summarising, setSummarising] = useState(false)
  const [highlights, setHighlights] = useState([])
  const [highlightsLoading, setHighlightsLoading] = useState(false)
  const [myRole, setMyRole] = useState('member')

  // Group edit state
  const [editing, setEditing] = useState(false)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [editLoading, setEditLoading] = useState(false)

  // Add member search state
  const [addSearch, setAddSearch] = useState('')
  const [addResults, setAddResults] = useState([])
  const [addSearching, setAddSearching] = useState(false)

  const convId = activeConversation?.id

  // Derive active group tab from prop or default
  const groupTab = (activeConversation?.isGroup ? activeTab : null) || 'members'

  useEffect(() => {
    if (!activeConversation?.isGroup) { setMembers([]); setMyRole('member'); return }
    client.get(`/groups/${activeConversation.id}`)
      .then((r) => {
        setMembers(r.data.members || [])
        const me = (r.data.members || []).find((m) => m.user_id === currentUser?.user_id)
        setMyRole(me?.role || 'member')
      })
      .catch(() => {})
  }, [activeConversation?.id])

  const handleSummary = async () => {
    if (!activeConversation?.isGroup) return
    setSummarising(true)
    setSummary(null)
    setActionItems([])
    setCheckedItems({})
    try {
      const r = await client.post('/ai/summarise', { group_id: activeConversation.id, days: 14 })
      setSummary(r.data.summary)
      setActionItems(r.data.action_items || [])
    } catch { toast.error('Summary failed') } finally { setSummarising(false) }
  }

  const handleHighlights = async () => {
    if (!activeConversation?.isGroup) return
    setHighlights([])
    setHighlightsLoading(true)
    try {
      const msgs = (useChatStore.getState().messages[convId] || [])
        .filter((m) => m.media_type === 'text' && !m.deleted)
        .slice(-50)
        .map((m) => ({ message_id: m.message_id, sender_name: m.sender_name || m.sender_id?.slice(0,8) || 'User', content: m.content }))
      if (msgs.length === 0) { toast('No messages to analyse'); return }
      const r = await client.post('/ai/highlights', { messages: msgs })
      setHighlights(r.data.highlights || [])
      if (!r.data.highlights?.length) toast('No highlights found in recent messages')
    } catch { toast.error('Highlights failed') } finally { setHighlightsLoading(false) }
  }

  const handleEditSave = async () => {
    if (!editName.trim()) return
    setEditLoading(true)
    try {
      await client.put(`/groups/${convId}`, { group_name: editName.trim(), description: editDesc.trim() })
      useChatStore.getState().updateGroup(convId, { group_name: editName.trim(), description: editDesc.trim() })
      toast.success('Group updated')
      setEditing(false)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Update failed')
    } finally { setEditLoading(false) }
  }

  const handleDeleteGroup = async () => {
    if (!window.confirm(`Delete "${activeConversation.name}"? This cannot be undone.`)) return
    try {
      await client.delete(`/groups/${convId}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Delete failed')
    }
  }

  const handleRoleToggle = async (member) => {
    const newRole = member.role === 'admin' ? 'member' : 'admin'
    try {
      await client.put(`/groups/${convId}/members/${member.user_id}/role`, { role: newRole })
      setMembers((prev) => prev.map((m) => m.user_id === member.user_id ? { ...m, role: newRole } : m))
      toast.success(`${member.display_name} is now ${newRole === 'admin' ? 'an admin' : 'a member'}`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to update role')
    }
  }

  const handleRemoveMember = async (member) => {
    if (!window.confirm(`Remove ${member.display_name} from the group?`)) return
    try {
      await client.delete(`/groups/${convId}/members/${member.user_id}`)
      setMembers((prev) => prev.filter((m) => m.user_id !== member.user_id))
      toast.success(`${member.display_name} removed`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to remove member')
    }
  }

  const handleAddSearch = async (q) => {
    setAddSearch(q)
    if (q.length < 2) { setAddResults([]); return }
    setAddSearching(true)
    try {
      const r = await client.get(`/users/search?q=${encodeURIComponent(q)}`)
      const existingIds = new Set(members.map((m) => m.user_id))
      setAddResults(r.data.filter((u) => !existingIds.has(u.user_id)))
    } catch { setAddResults([]) }
    finally { setAddSearching(false) }
  }

  const handleAddMember = async (u) => {
    try {
      await client.post(`/groups/${convId}/members`, { user_id: u.user_id })
      setMembers((prev) => [...prev, { user_id: u.user_id, display_name: u.display_name, role: 'member', user_presence: 'offline' }])
      setAddSearch('')
      setAddResults([])
      toast.success(`${u.display_name} added`)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add member')
    }
  }

  const isAdmin = myRole === 'admin'

  return (
    <div className="w-80 flex flex-col bg-white border-l border-slate-100 flex-shrink-0 shadow-sm">
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
          convId={convId}
          groupTab={groupTab}
          onTabChange={onTabChange}
          members={members}
          myRole={myRole}
          isAdmin={isAdmin}
          summary={summary}
          actionItems={actionItems}
          checkedItems={checkedItems}
          onToggleCheck={(i) => setCheckedItems(prev => ({ ...prev, [i]: !prev[i] }))}
          summarising={summarising}
          onSummary={handleSummary}
          editing={editing}
          editName={editName}
          editDesc={editDesc}
          editLoading={editLoading}
          onEditStart={() => { setEditName(activeConversation.name); setEditDesc(''); setEditing(true) }}
          onEditCancel={() => setEditing(false)}
          onEditNameChange={setEditName}
          onEditDescChange={setEditDesc}
          onEditSave={handleEditSave}
          onDeleteGroup={handleDeleteGroup}
          onRoleToggle={handleRoleToggle}
          onRemoveMember={handleRemoveMember}
          addSearch={addSearch}
          addResults={addResults}
          addSearching={addSearching}
          onAddSearch={handleAddSearch}
          onAddMember={handleAddMember}
          currentUserId={currentUser?.user_id}
          convName={activeConversation.name}
          highlights={highlights}
          highlightsLoading={highlightsLoading}
          onHighlights={handleHighlights}
          t={t}
        />
      ) : (
        /* DM: full AI assistant panel */
        <InlineAIChat
          key={convId}
          convId={convId}
          convName={activeConversation.name}
          isGroup={false}
          otherUserId={convId}
        />
      )}
    </div>
  )
}

// ─── Group panel ──────────────────────────────────────────────────────────────

function GroupPanel({
  convId, groupTab, onTabChange, members, myRole, isAdmin,
  summary, actionItems, checkedItems, onToggleCheck, summarising, onSummary,
  highlights, highlightsLoading, onHighlights,
  editing, editName, editDesc, editLoading,
  onEditStart, onEditCancel, onEditNameChange, onEditDescChange, onEditSave, onDeleteGroup,
  onRoleToggle, onRemoveMember,
  addSearch, addResults, addSearching, onAddSearch, onAddMember,
  currentUserId, convName, t,
}) {
  return (
    <>
      {/* Tab bar — Members | Summary | AI */}
      <div className="flex border-b border-slate-100 text-xs font-semibold flex-shrink-0">
        {[
          { key: 'members', label: 'Members', icon: <Users size={12} /> },
          { key: 'summary', label: 'Summary', icon: <Sparkles size={12} /> },
          { key: 'ai', label: 'AI', icon: <Bot size={12} /> },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => onTabChange?.(tab.key)}
            className={`flex-1 py-2.5 flex items-center justify-center gap-1 transition-all ${
              groupTab === tab.key
                ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/30'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>

      {groupTab === 'members' && (
        <div className="flex-1 overflow-y-auto scrollbar-thin flex flex-col">
          {isAdmin && (
            <div className="px-3 py-2 border-b border-slate-100">
              {editing ? (
                <div className="space-y-2">
                  <input
                    value={editName}
                    onChange={(e) => onEditNameChange(e.target.value)}
                    placeholder="Group name"
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300"
                  />
                  <input
                    value={editDesc}
                    onChange={(e) => onEditDescChange(e.target.value)}
                    placeholder="Description (optional)"
                    className="w-full px-2.5 py-1.5 text-xs border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300"
                  />
                  <div className="flex gap-1.5">
                    <button
                      onClick={onEditSave}
                      disabled={editLoading || !editName.trim()}
                      className="flex-1 py-1.5 text-xs text-white rounded-lg font-semibold disabled:opacity-50 transition-all"
                      style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
                    >
                      {editLoading ? <Loader2 size={12} className="inline animate-spin" /> : 'Save'}
                    </button>
                    <button
                      onClick={onEditCancel}
                      className="px-3 py-1.5 text-xs text-slate-500 hover:text-slate-700 border border-slate-200 rounded-lg transition-all"
                    >
                      Cancel
                    </button>
                  </div>
                  <button
                    onClick={onDeleteGroup}
                    className="w-full py-1.5 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 border border-red-100 rounded-lg transition-all font-semibold"
                  >
                    <Trash2 size={11} className="inline mr-1" /> Delete Group
                  </button>
                </div>
              ) : (
                <button
                  onClick={onEditStart}
                  className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-violet-600 hover:bg-violet-50 px-2 py-1.5 rounded-lg w-full transition-all"
                >
                  <Pencil size={12} /> Edit group
                </button>
              )}
            </div>
          )}

          <div className="flex-1 overflow-y-auto">
            {members.map((m) => (
              <div key={m.user_id} className="flex items-center gap-2 px-3 py-2.5 hover:bg-slate-50 transition-all group">
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
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-semibold text-slate-800 truncate">{m.display_name}</p>
                  {m.role === 'admin' && (
                    <span className="text-xs font-medium text-violet-600">admin</span>
                  )}
                </div>
                {isAdmin && m.user_id !== currentUserId && (
                  <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => onRoleToggle(m)}
                      className={`p-1 rounded-md transition-all ${
                        m.role === 'admin'
                          ? 'text-violet-400 hover:text-violet-600 hover:bg-violet-50'
                          : 'text-slate-400 hover:text-violet-600 hover:bg-violet-50'
                      }`}
                      title={m.role === 'admin' ? 'Remove admin' : 'Make admin'}
                    >
                      {m.role === 'admin' ? <ShieldOff size={13} /> : <Shield size={13} />}
                    </button>
                    <button
                      onClick={() => onRemoveMember(m)}
                      className="p-1 rounded-md text-slate-400 hover:text-red-500 hover:bg-red-50 transition-all"
                      title="Remove from group"
                    >
                      <UserMinus size={13} />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>

          {isAdmin && (
            <div className="px-3 py-2 border-t border-slate-100">
              <div className="relative">
                <UserPlus size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  value={addSearch}
                  onChange={(e) => onAddSearch(e.target.value)}
                  placeholder="Add member…"
                  className="w-full pl-7 pr-2 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-violet-300"
                />
              </div>
              {addSearching && <p className="text-xs text-slate-400 mt-1">Searching…</p>}
              {addResults.length > 0 && (
                <div className="mt-1 border border-slate-100 rounded-lg overflow-hidden max-h-28 overflow-y-auto">
                  {addResults.map((u) => (
                    <button
                      key={u.user_id}
                      onClick={() => onAddMember(u)}
                      className="w-full flex items-center gap-2 px-2 py-1.5 hover:bg-violet-50 text-left transition-all"
                    >
                      <div
                        className="w-5 h-5 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                        style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
                      >
                        {u.display_name.slice(0, 1).toUpperCase()}
                      </div>
                      <span className="text-xs text-slate-700 font-medium truncate">{u.display_name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {groupTab === 'summary' && (
        <div className="flex-1 overflow-y-auto p-3 scrollbar-thin space-y-3">
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
            <div
              className="p-3 rounded-xl text-xs text-slate-700 leading-relaxed border border-indigo-100"
              style={{ background: 'linear-gradient(135deg, #f0f4ff, #f5f3ff)' }}
            >
              <div className="flex items-center gap-1.5 mb-2">
                <Sparkles size={11} className="text-indigo-500" />
                <span className="text-xs font-bold text-indigo-600">AI Summary · Last 14 days</span>
              </div>
              <p className="whitespace-pre-wrap">{summary}</p>
            </div>
          )}

          {actionItems.length > 0 && (
            <div className="border border-amber-200 rounded-xl overflow-hidden"
                 style={{ background: 'linear-gradient(135deg, #fffbeb, #fefce8)' }}>
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-amber-100">
                <CheckSquare size={12} className="text-amber-500" />
                <span className="text-xs font-bold text-amber-700">Action Items</span>
                <span className="ml-auto text-xs text-amber-500 font-medium">
                  {Object.values(checkedItems).filter(Boolean).length}/{actionItems.length}
                </span>
              </div>
              <div className="p-2 space-y-1">
                {actionItems.map((item, i) => (
                  <button
                    key={i}
                    onClick={() => onToggleCheck(i)}
                    className="w-full flex items-start gap-2 text-left px-2 py-1.5 rounded-lg hover:bg-amber-50 transition-all"
                  >
                    {checkedItems[i]
                      ? <CheckSquare size={13} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                      : <Square size={13} className="text-amber-400 flex-shrink-0 mt-0.5" />
                    }
                    <span className={`text-xs leading-relaxed ${checkedItems[i] ? 'line-through text-slate-400' : 'text-slate-700'}`}>
                      {item}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Smart Highlights */}
          <button
            onClick={onHighlights}
            disabled={highlightsLoading}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-semibold transition-all disabled:opacity-60"
            style={{ background: 'linear-gradient(135deg, #fefce8, #fef9c3)', color: '#ca8a04' }}
          >
            {highlightsLoading ? <Loader2 size={14} className="animate-spin" /> : <Star size={14} />}
            Smart Highlights
          </button>

          {highlights.length > 0 && (
            <div className="border border-yellow-200 rounded-xl overflow-hidden"
                 style={{ background: 'linear-gradient(135deg, #fefce8, #fffbeb)' }}>
              <div className="flex items-center gap-1.5 px-3 py-2 border-b border-yellow-100">
                <Star size={12} className="text-yellow-500" />
                <span className="text-xs font-bold text-yellow-700">Important Messages</span>
              </div>
              <div className="p-2 space-y-2">
                {highlights.map((h, i) => (
                  <div key={i} className="px-2 py-2 bg-white/70 rounded-lg border border-yellow-100">
                    <p className="text-xs font-semibold text-yellow-700 mb-0.5">{h.reason}</p>
                    <p className="text-xs text-slate-600 leading-relaxed line-clamp-2">{h.content}</p>
                    <p className="text-xs text-slate-400 mt-0.5">— {h.sender_name}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {groupTab === 'ai' && (
        <InlineAIChat
          key={`group-${convId}`}
          convId={convId}
          convName={convName}
          isGroup={true}
          otherUserId={null}
        />
      )}
    </>
  )
}

// ─── Inline AI chat (used for DMs always, and Group AI tab) ──────────────────

const EMOJIS = ['😊','👍','❤️','🎉','😂','🤔','👏','🙏','💡','✅','⚡','🔥','💯','🚀','📌','✨','🎯','👀','💬','🔍','⭐','📝','🎨','🔔']

function _makeThread(convName, isGroup) {
  const ctx = convName
    ? (isGroup ? `📋 ${convName} group` : `💬 chat with ${convName}`)
    : 'your conversations'
  return {
    id: Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    name: 'New Thread',
    messages: [{
      role: 'bot',
      text: `Hi! ✨ I'm your AI assistant for ${ctx}. Ask me to search messages, summarise the conversation, or find anything!`,
    }],
  }
}

function InlineAIChat({ convId, convName, isGroup, otherUserId }) {
  const threadsKey = `aiThreads_${convId || 'global'}`

  const [threads, setThreads] = useState(() => {
    try {
      const stored = localStorage.getItem(threadsKey)
      if (stored) {
        const parsed = JSON.parse(stored)
        if (Array.isArray(parsed) && parsed.length > 0) return parsed
      }
    } catch {}
    return [_makeThread(convName, isGroup)]
  })

  const [activeIdx, setActiveIdx] = useState(0)
  const [showThreads, setShowThreads] = useState(false)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [listening, setListening] = useState(false)
  const [showEmoji, setShowEmoji] = useState(false)
  const bottomRef = useRef(null)
  const fileInputRef = useRef()
  const recRef = useRef(null)

  const safeIdx = Math.min(activeIdx, threads.length - 1)
  const activeThread = threads[safeIdx]
  const msgs = activeThread?.messages || []

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs.length])

  useEffect(() => {
    try {
      localStorage.setItem(threadsKey, JSON.stringify(threads.slice(-10)))
    } catch {}
  }, [threads, threadsKey])

  const updateThread = (idx, fn) =>
    setThreads(prev => { const next = [...prev]; next[idx] = fn(next[idx]); return next })

  const send = async (text) => {
    const t = (text || input).trim()
    if (!t || loading) return
    setInput('')
    setShowEmoji(false)
    const curIdx = safeIdx

    updateThread(curIdx, th => ({
      ...th,
      name: th.name === 'New Thread' ? t.slice(0, 28) : th.name,
      messages: [...th.messages, { role: 'user', text: t }],
    }))
    setLoading(true)
    try {
      const res = await client.post('/ai/chat', {
        message: t,
        session_id: threads[curIdx]?.id,
        conv_id: convId,
        is_group: isGroup || false,
        conv_name: convName,
        other_user_id: otherUserId,
      })
      updateThread(curIdx, th => ({
        ...th,
        messages: [...th.messages, {
          role: 'bot',
          text: res.data.text || 'No response.',
          toolCalls: res.data.tool_calls || [],
        }],
      }))
    } catch {
      updateThread(curIdx, th => ({
        ...th,
        messages: [...th.messages, { role: 'bot', text: '⚠️ Something went wrong. Please try again.' }],
      }))
    } finally { setLoading(false) }
  }

  const newThread = () => {
    const t = _makeThread(convName, isGroup)
    setThreads(prev => [...prev, t])
    setActiveIdx(threads.length)
    setShowThreads(false)
  }

  const deleteThread = (idx, e) => {
    e.stopPropagation()
    if (threads.length === 1) { setThreads([_makeThread(convName, isGroup)]); setActiveIdx(0); return }
    client.delete(`/ai/chat/session/${threads[idx].id}`).catch(() => {})
    setThreads(prev => prev.filter((_, i) => i !== idx))
    setActiveIdx(prev => (prev >= idx ? Math.max(0, prev - 1) : prev))
    setShowThreads(false)
  }

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { import('react-hot-toast').then(m => m.default.error('Voice not supported in this browser')); return }
    const rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = false
    rec.onresult = (e) => setInput(prev => prev + e.results[0][0].transcript + ' ')
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recRef.current = rec
    rec.start()
    setListening(true)
  }
  const stopVoice = () => { recRef.current?.stop(); setListening(false) }

  const handleFile = (e) => {
    const file = e.target.files[0]
    if (!file) return
    const isText = file.type.startsWith('text/') || /\.(txt|md|csv|json|xml|html|js|py|ts)$/i.test(file.name)
    if (isText) {
      const reader = new FileReader()
      reader.onload = (ev) => {
        const text = ev.target.result
        send(`📎 [Document: ${file.name}]\n\n${text.slice(0, 1500)}${text.length > 1500 ? '\n...(truncated)' : ''}`)
      }
      reader.readAsText(file)
    } else {
      send(`📎 I've uploaded a file: **${file.name}** (${(file.size / 1024).toFixed(1)} KB). Can you help me with anything related to this?`)
    }
    e.target.value = ''
  }

  const STARTERS = isGroup
    ? [`Summarize ${convName || 'this group'}`, 'What was decided recently? 🤔', 'Show me unread images 🖼️']
    : [`Summarize my chat with ${convName || 'this person'} 📋`, 'What did we discuss? 💬', 'Show me unread images 🖼️']

  return (
    <div className="flex flex-col flex-1 overflow-hidden relative">
      {/* Header */}
      <div className="px-3 py-2 flex items-center gap-2 border-b border-slate-100 flex-shrink-0"
           style={{ background: 'linear-gradient(to right, #f0f4ff, #f5f3ff)' }}>
        <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0"
             style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}>
          <Sparkles size={11} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-indigo-700 leading-tight truncate">
            {activeThread?.name || 'AI Assistant'}
          </p>
          <p className="text-xs text-slate-400 leading-tight">Powered by Gemini ✨</p>
        </div>
        <div className="flex gap-0.5 flex-shrink-0">
          <button onClick={() => setShowThreads(v => !v)}
            className={`p-1 rounded-lg transition-all ${showThreads ? 'text-indigo-500 bg-indigo-100' : 'text-slate-400 hover:text-indigo-500'}`}
            title="Conversations">
            <MessageSquare size={13} />
          </button>
          <button onClick={newThread}
            className="p-1 text-slate-400 hover:text-indigo-500 rounded-lg transition-all"
            title="New thread">
            <Plus size={13} />
          </button>
        </div>
      </div>

      {/* Thread list overlay */}
      {showThreads && (
        <div className="absolute inset-x-0 z-20 bg-white border-b border-slate-100 shadow-lg"
             style={{ top: 44 }}>
          <div className="px-3 py-1.5 border-b border-slate-100 flex items-center justify-between">
            <span className="text-xs font-bold text-slate-700">Conversations</span>
            <button onClick={() => setShowThreads(false)}
              className="p-0.5 text-slate-400 hover:text-slate-600 rounded transition-all">
              <X size={12} />
            </button>
          </div>
          <div className="max-h-44 overflow-y-auto scrollbar-thin">
            {threads.map((th, i) => (
              <div key={th.id} onClick={() => { setActiveIdx(i); setShowThreads(false) }}
                className={`flex items-center gap-2 px-3 py-2 cursor-pointer group transition-all ${
                  i === safeIdx ? 'bg-indigo-50' : 'hover:bg-slate-50'
                }`}>
                <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${i === safeIdx ? 'bg-indigo-500' : 'bg-slate-200'}`} />
                <span className={`text-xs flex-1 truncate ${i === safeIdx ? 'text-indigo-700 font-semibold' : 'text-slate-600'}`}>
                  {th.name}
                </span>
                <button onClick={(e) => deleteThread(i, e)}
                  className="text-slate-300 hover:text-red-400 text-sm leading-none flex-shrink-0 opacity-0 group-hover:opacity-100 transition-all px-1">
                  ×
                </button>
              </div>
            ))}
          </div>
          <div className="px-3 py-1.5 border-t border-slate-100">
            <button onClick={newThread}
              className="w-full flex items-center justify-center gap-1 py-1.5 text-xs font-semibold text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all">
              <Plus size={11} /> New Thread
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-2.5 space-y-2 scrollbar-thin">
        {msgs.map((msg, i) => (
          <div key={i}>
            <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[88%] text-xs rounded-xl px-3 py-2 leading-relaxed ${
                  msg.role === 'user'
                    ? 'text-white rounded-br-sm shadow-sm'
                    : 'bg-slate-50 text-slate-700 border border-slate-100 rounded-bl-sm'
                }`}
                style={msg.role === 'user' ? { background: 'linear-gradient(135deg, #6366f1, #7c3aed)' } : {}}
              >
                {msg.role === 'bot' && (
                  <span className="flex items-center gap-1 mb-1">
                    <Sparkles size={9} className="text-indigo-400" />
                    <span className="text-xs text-indigo-500 font-semibold">AI ✨</span>
                  </span>
                )}
                <p className="whitespace-pre-wrap break-words">{msg.text}</p>
              </div>
            </div>
            {msg.toolCalls?.length > 0 && (
              <div className="mt-1 space-y-1">
                {msg.toolCalls.map((tc, j) => <MiniToolCard key={j} tc={tc} />)}
              </div>
            )}
          </div>
        ))}
        {loading && (
          <div className="flex items-center gap-1.5 text-indigo-400 text-xs px-1">
            <Loader2 size={11} className="animate-spin" /> Thinking… ✨
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Quick starters (first message only) */}
      {msgs.length === 1 && (
        <div className="px-2.5 pb-1 space-y-1 flex-shrink-0">
          {STARTERS.map((ex) => (
            <button key={ex} onClick={() => send(ex)}
              className="w-full text-left text-xs text-indigo-600 hover:bg-indigo-50 px-2.5 py-1.5 rounded-lg transition-all font-medium truncate">
              "{ex}"
            </button>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="p-2 border-t border-slate-100 flex-shrink-0">
        {showEmoji && (
          <div className="mb-1.5 bg-white border border-slate-200 rounded-xl p-1.5 grid grid-cols-6 gap-0.5 shadow-md">
            {EMOJIS.map(em => (
              <button key={em} onClick={() => { setInput(p => p + em); setShowEmoji(false) }}
                className="text-base hover:bg-slate-100 rounded-lg p-0.5 transition-all leading-none">
                {em}
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-1 items-center">
          <button onClick={() => setShowEmoji(v => !v)}
            className={`p-1 rounded-lg transition-all flex-shrink-0 text-base leading-none ${showEmoji ? 'bg-indigo-50' : 'opacity-70 hover:opacity-100'}`}
            title="Emoji">
            😊
          </button>
          <button onClick={() => fileInputRef.current?.click()}
            className="p-1 text-slate-400 hover:text-indigo-500 rounded-lg transition-all flex-shrink-0"
            title="Upload document">
            <Paperclip size={13} />
          </button>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
            placeholder="Ask AI…"
            className="flex-1 min-w-0 px-2 py-1.5 bg-slate-50 border border-slate-200 rounded-xl text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-300 transition-all"
          />
          <button onClick={listening ? stopVoice : startVoice}
            className={`p-1 rounded-lg transition-all flex-shrink-0 ${listening ? 'text-red-500 bg-red-50 animate-pulse' : 'text-slate-400 hover:text-indigo-500'}`}
            title={listening ? 'Stop' : 'Voice input'}>
            <Mic size={13} />
          </button>
          <button onClick={() => send()} disabled={!input.trim() || loading}
            className="p-1.5 text-white rounded-xl disabled:opacity-40 transition-all flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}>
            <Send size={12} />
          </button>
        </div>
        <input ref={fileInputRef} type="file" className="hidden" onChange={handleFile}
          accept=".txt,.md,.csv,.json,.xml,.html,.js,.py,.ts,.pdf,.doc,.docx" />
      </div>
    </div>
  )
}

function MiniToolCard({ tc }) {
  const [open, setOpen] = useState(false)
  const { setActiveConversation } = useChatStore()
  const result = tc.result
  const isImageTool = tc.tool === 'fetch_unread_images'
  const count = Array.isArray(result) ? result.length : (result?.summary ? 1 : 0)

  const navigateTo = (img) => {
    if (img.group_id) {
      setActiveConversation({ id: img.group_id, name: img.group_name || 'Group', isGroup: true })
    } else if (img.receiver_id) {
      setActiveConversation({ id: img.sender_id, name: 'DM', isGroup: false })
    }
  }

  return (
    <div className="bg-white border border-indigo-100 rounded-lg overflow-hidden">
      <button onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-2.5 py-1.5 text-xs hover:bg-indigo-50/50 transition-all">
        <span className="font-semibold text-indigo-600 truncate">
          {isImageTool ? '🖼️' : '🔧'} {tc.tool}
        </span>
        <span className="text-slate-400 flex-shrink-0 ml-1">{count > 0 ? count : ''} {open ? '▲' : '▼'}</span>
      </button>
      {open && result && (
        <div className="px-2.5 pb-2 space-y-1">
          {isImageTool && Array.isArray(result) ? (
            result.length === 0 ? (
              <p className="text-xs text-slate-400 italic py-1">No unread images found.</p>
            ) : (
              <div className="grid grid-cols-2 gap-1.5 pt-1">
                {result.map((img, i) => (
                  <button
                    key={i}
                    onClick={() => navigateTo(img)}
                    className="relative group rounded-lg overflow-hidden border border-slate-100 hover:border-indigo-300 transition-all aspect-square bg-slate-50"
                    title={img.group_name || 'Go to chat'}
                  >
                    <img
                      src={resolveUrl(img.media_url)}
                      alt={img.content || 'image'}
                      className="w-full h-full object-cover"
                      onError={(e) => { e.target.style.display = 'none' }}
                    />
                    <div className="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-all flex items-center justify-center opacity-0 group-hover:opacity-100">
                      <ExternalLink size={14} className="text-white" />
                    </div>
                    {img.group_name && (
                      <div className="absolute bottom-0 inset-x-0 bg-black/50 px-1 py-0.5">
                        <p className="text-white text-xs truncate leading-tight">{img.group_name}</p>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )
          ) : Array.isArray(result) ? (
            result.slice(0, 3).map((r, i) => (
              <p key={i} className="text-xs text-slate-600 bg-indigo-50/50 rounded-md p-1.5 truncate">
                {r.content || JSON.stringify(r).slice(0, 80)}
              </p>
            ))
          ) : (
            <p className="text-xs text-slate-600 whitespace-pre-wrap break-words">
              {result?.summary || result?.error || JSON.stringify(result).slice(0, 150)}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
