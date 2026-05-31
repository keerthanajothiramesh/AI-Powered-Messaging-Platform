import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Users, MessageSquare, Plus } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'

export default function ConversationList({ onCreateGroup }) {
  const { t } = useTranslation()
  const { groups, setGroups, setActiveConversation, activeConversation } = useChatStore()
  const { user } = useAuthStore()
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [activeTab, setActiveTab] = useState('groups')
  const [dmConversations, setDmConversations] = useState([])

  useEffect(() => {
    client.get('/groups/me').then((r) => setGroups(r.data)).catch(() => {})
    client.get('/messages/dm/conversations').then((r) => setDmConversations(r.data)).catch(() => {})
  }, [])

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
      <div className="p-4 border-b border-gray-100">
        <div className="relative">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder={t('search.placeholder')}
            className="w-full pl-9 pr-3 py-2 bg-gray-50 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
          />
        </div>
      </div>

      <div className="flex border-b border-gray-100 text-xs font-medium">
        <button
          onClick={() => setActiveTab('groups')}
          className={`flex-1 py-2 flex items-center justify-center gap-1 ${activeTab === 'groups' ? 'text-primary border-b-2 border-primary' : 'text-gray-500'}`}
        >
          <Users size={14} /> Groups
        </button>
        <button
          onClick={() => setActiveTab('dms')}
          className={`flex-1 py-2 flex items-center justify-center gap-1 ${activeTab === 'dms' ? 'text-primary border-b-2 border-primary' : 'text-gray-500'}`}
        >
          <MessageSquare size={14} /> Direct
        </button>
      </div>

      <div className="flex-1 overflow-y-auto scrollbar-thin">
        {activeTab === 'groups' && (
          <>
            <div className="p-2">
              <button
                onClick={onCreateGroup}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-primary hover:bg-red-50 rounded-lg transition-colors"
              >
                <Plus size={16} /> {t('groups.create')}
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
                onClick={() => setActiveConversation({ id: g.group_id, name: g.group_name, isGroup: true })}
              />
            ))}
          </>
        )}

        {activeTab === 'dms' && (
          <>
            {search.length >= 2
              ? searchResults.map((u) => (
                  <ConvItem
                    key={u.user_id}
                    id={u.user_id}
                    name={u.display_name}
                    subtitle={u.user_presence}
                    isActive={activeConversation?.id === u.user_id}
                    presence={u.user_presence}
                    onClick={() => setActiveConversation({ id: u.user_id, name: u.display_name, isGroup: false })}
                  />
                ))
              : dmConversations.length > 0
                ? dmConversations.map((u) => (
                    <ConvItem
                      key={u.user_id}
                      id={u.user_id}
                      name={u.display_name}
                      subtitle={u.last_message || u.user_presence}
                      isActive={activeConversation?.id === u.user_id}
                      presence={u.user_presence}
                      onClick={() => setActiveConversation({ id: u.user_id, name: u.display_name, isGroup: false })}
                    />
                  ))
                : (
                    <p className="text-center text-xs text-gray-400 p-4">
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

function ConvItem({ id, name, subtitle, isGroup, isActive, presence, onClick }) {
  const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 transition-colors text-left ${isActive ? 'bg-red-50 border-r-2 border-primary' : ''}`}
    >
      <div className="relative flex-shrink-0">
        <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold text-white ${isGroup ? 'bg-primary' : 'bg-gray-400'}`}>
          {initials}
        </div>
        {!isGroup && (
          <span className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white ${presence === 'online' ? 'bg-green-500' : 'bg-gray-400'}`} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900 truncate">{name}</p>
        <p className="text-xs text-gray-500 truncate">{subtitle}</p>
      </div>
    </button>
  )
}
