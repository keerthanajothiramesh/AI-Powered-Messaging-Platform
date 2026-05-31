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
    <div className="flex h-screen overflow-hidden" style={{ background: '#eef2ff' }}>
      {/* Left sidebar — dark indigo/violet gradient */}
      <aside className="w-72 flex flex-col flex-shrink-0"
             style={{ background: 'linear-gradient(180deg, #1e1b4b 0%, #2d1b69 50%, #2e1065 100%)' }}>
        <div className="px-4 py-4 border-b border-white/10 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl flex items-center justify-center shadow-lg flex-shrink-0"
               style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}>
            <MessageSquare size={18} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-white truncate">{t('app.name')}</p>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          <ConversationList onCreateGroup={() => setShowGroupModal(true)} />
        </div>

        <div className="px-4 py-3 border-t border-white/10 flex items-center gap-2.5">
          <button
            onClick={() => setShowSettings(true)}
            className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold hover:opacity-90 transition-opacity shadow-md flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
            title="Settings & profile"
          >
            {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-white truncate">{user?.display_name}</p>
            <p className="text-xs text-emerald-400 font-medium">● online</p>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 text-white/40 hover:text-white rounded-lg hover:bg-white/10 transition-all"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex overflow-hidden">
        {showAI ? <AIAssistantPanel onClose={() => setShowAI(false)} /> : <ChatWindow />}
      </main>

      {/* Right panel */}
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
