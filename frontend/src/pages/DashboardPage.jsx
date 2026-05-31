import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageSquare, LogOut } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import ConversationList from '../components/ConversationList'
import ChatWindow from '../components/ChatWindow'
import RightPanel from '../components/RightPanel'
import AIAssistantPanel from '../components/AIAssistantPanel'
import SearchModal from '../components/SearchModal'
import GroupModal from '../components/GroupModal'
import SettingsModal from '../components/SettingsModal'
import client from '../api/client'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'

export default function DashboardPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [showAI, setShowAI] = useState(false)
  const [showSearch, setShowSearch] = useState(false)
  const [showGroupModal, setShowGroupModal] = useState(false)
  const [showSettings, setShowSettings] = useState(false)

  useWebSocket()

  const handleLogout = async () => {
    try { await client.post('/auth/logout') } catch {}
    logout()
    navigate('/login')
    toast.success('Logged out')
  }

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Left sidebar */}
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
          <button
            onClick={() => setShowSettings(true)}
            className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white text-xs font-semibold hover:opacity-80 transition-opacity"
            title="Settings & profile"
          >
            {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-900 truncate">{user?.display_name}</p>
            <p className="text-xs text-green-500">● online</p>
          </div>
          <button onClick={handleLogout} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors">
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex overflow-hidden">
        {showAI ? <AIAssistantPanel onClose={() => setShowAI(false)} /> : <ChatWindow />}
      </main>

      {/* Right panel — always visible, hosts the toolbar */}
      <RightPanel
        onSearchOpen={() => setShowSearch(true)}
        showAI={showAI}
        onAIToggle={() => setShowAI((p) => !p)}
        onSettingsOpen={() => setShowSettings(true)}
      />

      {showSearch && <SearchModal onClose={() => setShowSearch(false)} />}
      {showGroupModal && <GroupModal onClose={() => setShowGroupModal(false)} />}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} onSignOut={handleLogout} />}
    </div>
  )
}
