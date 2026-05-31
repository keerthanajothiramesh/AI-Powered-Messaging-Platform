import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Users, Loader2, Sparkles, Search, Bot, Settings, Mail, Clock, Mic, Video, FileText, Pencil, Trash2, Shield, ShieldOff, UserMinus, UserPlus, Check, X } from 'lucide-react'
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

export default function RightPanel({ onSearchOpen, showAI, onAIToggle, onSettingsOpen, activeTab, onTabChange }) {
  const { t, i18n } = useTranslation()
  const { activeConversation, messages } = useChatStore()
  const { user: currentUser } = useAuthStore()

  const [members, setMembers] = useState([])
  const [summary, setSummary] = useState(null)
  const [summarising, setSummarising] = useState(false)
  const [myRole, setMyRole] = useState('member')

  const [dmTab, setDmTab] = useState('info')
  const [otherUser, setOtherUser] = useState(null)
  const [userLoading, setUserLoading] = useState(false)

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
  const convMessages = messages[convId] || []
  const sharedMedia = convMessages.filter((m) => m.media_type !== 'text' && !m.deleted)

  // Derive active group tab from prop or default
  const groupTab = (activeConversation?.isGroup ? activeTab : null) || 'members'
  const dmTabActive = (!activeConversation?.isGroup ? activeTab : null) || 'info'

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
    <div className="w-64 flex flex-col bg-white border-l border-slate-100 flex-shrink-0 shadow-sm">
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
            showAI ? 'text-indigo-600 bg-indigo-50' : 'text-slate-500 hover:text-indigo-600 hover:bg-indigo-50'
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
          convId={convId}
          groupTab={groupTab}
          onTabChange={onTabChange}
          members={members}
          myRole={myRole}
          isAdmin={isAdmin}
          summary={summary}
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
          t={t}
        />
      ) : (
        <DmPanel
          dmTab={dmTabActive}
          onTabChange={onTabChange}
          otherUser={otherUser}
          userLoading={userLoading}
          sharedMedia={sharedMedia}
        />
      )}
    </div>
  )
}

function GroupPanel({
  convId, groupTab, onTabChange, members, myRole, isAdmin,
  summary, summarising, onSummary,
  editing, editName, editDesc, editLoading,
  onEditStart, onEditCancel, onEditNameChange, onEditDescChange, onEditSave, onDeleteGroup,
  onRoleToggle, onRemoveMember,
  addSearch, addResults, addSearching, onAddSearch, onAddMember,
  currentUserId, t,
}) {
  return (
    <>
      {/* Tab bar */}
      <div className="flex border-b border-slate-100 text-xs font-semibold">
        <button
          onClick={() => onTabChange?.('members')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1 transition-all ${
            groupTab === 'members' ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/30' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Users size={13} /> Members
        </button>
        <button
          onClick={() => onTabChange?.('summary')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1 transition-all ${
            groupTab === 'summary' ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/30' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          <Sparkles size={13} /> Summary
        </button>
      </div>

      {groupTab === 'members' ? (
        <div className="flex-1 overflow-y-auto scrollbar-thin flex flex-col">
          {/* Admin: Edit group name/description */}
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

          {/* Member list */}
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
                {/* Admin actions — shown on hover, hidden for self */}
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

          {/* Admin: Add member */}
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
      ) : (
        /* Summary tab */
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

function DmPanel({ dmTab, onTabChange, otherUser, userLoading, sharedMedia }) {
  return (
    <>
      <div className="flex border-b border-slate-100 text-xs font-semibold">
        <button
          onClick={() => onTabChange?.('info')}
          className={`flex-1 py-2.5 transition-all ${
            dmTab === 'info' ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/30' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Info
        </button>
        <button
          onClick={() => onTabChange?.('shared')}
          className={`flex-1 py-2.5 transition-all ${
            dmTab === 'shared' ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/30' : 'text-slate-500 hover:text-slate-700'
          }`}
        >
          Shared ({sharedMedia.length})
        </button>
      </div>

      {dmTab !== 'shared' ? (
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
