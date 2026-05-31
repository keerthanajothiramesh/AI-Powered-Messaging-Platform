import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageSquare, Search, Bot, Globe, LogOut, User } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import ConversationList from '../components/ConversationList'
import ChatWindow from '../components/ChatWindow'
import RightPanel from '../components/RightPanel'
import AIAssistantPanel from '../components/AIAssistantPanel'
import SearchModal from '../components/SearchModal'
import GroupModal from '../components/GroupModal'
import NotificationsDropdown from '../components/NotificationsDropdown'
import client from '../api/client'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'

export default function DashboardPage() {
  const { t, i18n } = useTranslation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [showAI, setShowAI] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [showGroupModal, setShowGroupModal] = useState(false)

  useWebSocket()

  const handleLogout = async () => {
    try { await client.post('/auth/logout') } catch {}
    logout()
    navigate('/login')
    toast.success('Logged out')
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <aside className="w-72 flex flex-col bg-white border-r border-gray-100 shadow-sm">
        <div className="px-4 py-4 border-b border-gray-100 flex items-center gap-3">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <MessageSquare size={18} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-gray-900 truncate">{t('app.name')}</p>
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <ConversationList onCreateGroup={() => setShowGroupModal(true)} />
        </div>
        <div className="px-4 py-3 border-t border-gray-100 flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white text-xs font-semibold">
            {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate">{user?.display_name}</p>
            <p className="text-xs text-green-500">● online</p>
          </div>
          <button onClick={handleLogout} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      <main className="flex-1 flex overflow-hidden">
        <ChatWindow />
      </main>

      {showAI && <AIAssistantPanel onClose={() => setShowAI(false)} />}
      {!showAI && (
        <aside className="flex flex-col">
          <RightPanel />
        </aside>
      )}

      <div className="fixed top-4 right-4 flex items-center gap-2 z-40">
        <button
          onClick={() => setShowSearch(true)}
          className="p-2 bg-white text-gray-600 rounded-xl shadow-sm hover:bg-gray-50 transition-colors"
          title={t('search.placeholder')}
        >
          <Search size={18} />
        </button>
        <button
          onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'ja' : 'en')}
          className="p-2 bg-white text-gray-600 rounded-xl shadow-sm hover:bg-gray-50 transition-colors text-sm"
        >
          {i18n.language === 'en' ? '🇯🇵' : '🇬🇧'}
        </button>
        <NotificationsDropdown />
        <button
          onClick={() => setShowAI(!showAI)}
          className={`p-2 rounded-xl shadow-sm transition-colors ${showAI ? 'bg-primary text-white' : 'bg-white text-gray-600 hover:bg-gray-50'}`}
          title={t('ai.assistant')}
        >
          <Bot size={18} />
        </button>
      </div>

      {showSearch && <SearchModal onClose={() => setShowSearch(false)} />}
      {showGroupModal && <GroupModal onClose={() => setShowGroupModal(false)} />}
    </div>
  )
}
