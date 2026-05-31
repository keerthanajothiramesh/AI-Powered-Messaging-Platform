import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Users, MessageSquare, Plus } from 'lucide-react'
import { format, isToday, isYesterday } from 'date-fns'
import { useChatStore } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'

function formatLastSeen(ts) {
  if (!ts) return 'offline'
  const d = new Date(ts)
  if (isToday(d)) return `last seen at ${format(d, 'HH:mm')}`
  if (isYesterday(d)) return 'last seen yesterday'
  return `last seen ${format(d, 'dd MMM')}`
}

export default function ConversationList({ onCreateGroup }) {
  const { t } = useTranslation()
  const { groups, setGroups, setActiveConversation, activeConversation, onlineUsers, lastSeen, unreadCounts, clearUnread, dmRefreshKey, setLastSeen } = useChatStore()
  const { user } = useAuthStore()
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [activeTab, setActiveTab] = useState('groups')
  const [dmConversations, setDmConversations] = useState([])

  useEffect(() => {
    client.get('/groups/me').then((r) => setGroups(r.data)).catch(() => {})
  }, [])

  useEffect(() => {
    client.get('/messages/dm/conversations').then((r) => setDmConversations(r.data)).catch(() => {})
  }, [dmRefreshKey])

  const handleSearch = async (q) => {
    setSearch(q)
    if (q.length < 2) { setSearchResults([]); return }
    try {
      const r = await client.get(`/users/search?q=${q}`)
      setSearchResults(r.data)
    } catch { setSearchResults([]) }
  }

  const filteredGroups = groups.filter((g) =>
    g.group_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-white/10">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/40" />
          <input
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder={t('search.placeholder')}
            className="w-full pl-9 pr-3 py-2 bg-white/10 border border-white/15 rounded-xl text-sm text-white placeholder:text-white/35 focus:outline-none focus:ring-2 focus:ring-indigo-400/40 focus:bg-white/15 transition-all"
          />
        </div>
      </div>

      <div className="flex border-b border-white/10 text-xs font-medium">
        <button
          onClick={() => setActiveTab('groups')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'groups'
              ? 'text-white border-b-2 border-violet-400'
              : 'text-white/45 hover:text-white/70'
          }`}
        >
          <Users size={13} /> Groups
        </button>
        <button
          onClick={() => setActiveTab('dms')}
          className={`flex-1 py-2.5 flex items-center justify-center gap-1.5 transition-all ${
            activeTab === 'dms'
              ? 'text-white border-b-2 border-violet-400'
              : 'text-white/45 hover:text-white/70'
          }`}
        >
          <MessageSquare size={13} /> Direct
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {activeTab === 'groups' && (
          <>
            <div className="p-2">
              <button
                onClick={onCreateGroup}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-indigo-300 hover:bg-white/10 rounded-xl transition-all font-medium"
              >
                <Plus size={15} /> {t('groups.create')}
              </button>
            </div>
            {filteredGroups.map((g) => (
              <ConvItem
                key={g.group_id}
                id={g.group_id}
                name={g.group_name}
                subtitle={`${g.member_count} members`}
                isGroup
                isActive={activeConversation?.id === g.group_id}
                unreadCount={unreadCounts[g.group_id] || 0}
                onClick={() => { setActiveConversation({ id: g.group_id, name: g.group_name, isGroup: true }); clearUnread(g.group_id) }}
              />
            ))}
          </>
        )}

        {activeTab === 'dms' && (
          <>
            {search.length >= 2
              ? searchResults.map((u) => {
                  const isOnline = onlineUsers.has(u.user_id)
                  return (
                    <ConvItem
                      key={u.user_id}
                      id={u.user_id}
                      name={u.display_name}
                      subtitle={isOnline ? 'Online' : formatLastSeen(lastSeen[u.user_id] || u.last_seen)}
                      isActive={activeConversation?.id === u.user_id}
                      isOnline={isOnline}
                      unreadCount={unreadCounts[u.user_id] || 0}
                      onClick={() => {
                        setActiveConversation({ id: u.user_id, name: u.display_name, isGroup: false })
                        clearUnread(u.user_id)
                        if (!isOnline && u.last_seen) setLastSeen(u.user_id, u.last_seen)
                      }}
                    />
                  )
                })
              : dmConversations.length > 0
                ? dmConversations.map((u) => {
                    const isOnline = onlineUsers.has(u.user_id)
                    return (
                      <ConvItem
                        key={u.user_id}
                        id={u.user_id}
                        name={u.display_name}
                        subtitle={u.last_message || (isOnline ? 'Online' : formatLastSeen(lastSeen[u.user_id] || u.last_seen))}
                        isActive={activeConversation?.id === u.user_id}
                        isOnline={isOnline}
                        unreadCount={unreadCounts[u.user_id] || 0}
                        onClick={() => {
                          setActiveConversation({ id: u.user_id, name: u.display_name, isGroup: false })
                          clearUnread(u.user_id)
                          if (!isOnline && u.last_seen) setLastSeen(u.user_id, u.last_seen)
                        }}
                      />
                    )
                  })
                : (
                    <p className="text-center text-xs text-white/30 p-4 mt-2">
                      Search for a user to start a conversation
                    </p>
                  )
            }
          </>
        )}
      </div>
    </div>
  )
}

function ConvItem({ id, name, subtitle, isGroup, isActive, isOnline, unreadCount, onClick }) {
  const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-3 py-3 hover:bg-white/10 transition-all text-left ${
        isActive ? 'bg-white/15 border-r-2 border-violet-400' : ''
      }`}
    >
      <div className="relative flex-shrink-0">
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white"
          style={{
            background: isGroup
              ? 'linear-gradient(135deg, #818cf8, #7c3aed)'
              : 'linear-gradient(135deg, #64748b, #475569)',
          }}
        >
          {initials}
        </div>
        {!isGroup && (
          <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 transition-colors ${
            isOnline ? 'bg-emerald-400 border-indigo-950' : 'bg-slate-500 border-indigo-950'
          }`} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-white truncate">{name}</p>
        <p className={`text-xs truncate mt-0.5 ${isOnline ? 'text-emerald-400 font-medium' : 'text-white/38'}`}>
          {subtitle}
        </p>
      </div>
      {unreadCount > 0 && (
        <span className="flex-shrink-0 min-w-[20px] h-5 rounded-full text-xs text-white flex items-center justify-center font-bold px-1"
              style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}>
          {unreadCount > 99 ? '99+' : unreadCount}
        </span>
      )}
    </button>
  )
}
