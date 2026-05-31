import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { MessageSquare, LogOut } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import { useWebSocket } from '../hooks/useWebSocket'
import ConversationList from '../components/ConversationList'
import ChatWindow from '../components/ChatWindow'
import RightPanel from '../components/RightPanel'
import SearchModal from '../components/SearchModal'
import GroupModal from '../components/GroupModal'
import SettingsModal from '../components/SettingsModal'
import UserInfoModal from '../components/UserInfoModal'
import SharedMediaModal from '../components/SharedMediaModal'
import CatchUpBanner, { CatchUpLoader } from '../components/CatchUpBanner'
import client from '../api/client'
import toast from 'react-hot-toast'
import { useNavigate } from 'react-router-dom'
import { useChatStore } from '../store/chatStore'

export default function DashboardPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const [showSearch, setShowSearch] = useState(false)
  const [showGroupModal, setShowGroupModal] = useState(false)
  const [showSettings, setShowSettings] = useState(false)

  // Controls which tab is shown in the RightPanel for groups (members | summary | ai)
  const [rightTab, setRightTab] = useState(null)

  // Info popup and shared media modal
  const [infoUserId, setInfoUserId] = useState(null)
  const [showSharedMedia, setShowSharedMedia] = useState(false)

  // Catch-up banner
  const [catchUpData, setCatchUpData] = useState(null)
  const [catchUpLoading, setCatchUpLoading] = useState(true)

  useEffect(() => {
    client.post('/ai/catchup', { hours_offline: 24 })
      .then((r) => setCatchUpData(r.data))
      .catch(() => {})
      .finally(() => setCatchUpLoading(false))
  }, [])

  const { activeConversation, setActiveConversation } = useChatStore()

  useWebSocket()

  const handleLogout = async () => {
    try { await client.post('/auth/logout') } catch {}
    logout()
    navigate('/login')
    toast.success('Logged out')
  }

  const handleInfoOpen = (userId) => setInfoUserId(userId)
  const handleSharedOpen = () => setShowSharedMedia(true)

  return (
    <div className="flex h-screen overflow-hidden bg-white">
      {/* Left sidebar */}
      <aside className="w-72 flex flex-col flex-shrink-0 bg-white border-r border-slate-100">
        <div className="px-4 py-4 border-b border-slate-100 flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center shadow-md flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
          >
            <MessageSquare size={18} className="text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-bold text-slate-800 truncate">{t('app.name')}</p>
          </div>
        </div>

        <div className="flex-1 overflow-hidden">
          <ConversationList onCreateGroup={() => setShowGroupModal(true)} />
        </div>

        <div className="px-4 py-3 border-t border-slate-100 flex items-center gap-2.5">
          <button
            onClick={() => setShowSettings(true)}
            className="w-9 h-9 rounded-xl flex items-center justify-center text-white text-xs font-bold hover:opacity-90 transition-opacity shadow-md flex-shrink-0"
            style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
            title="Settings & profile"
          >
            {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-800 truncate">{user?.display_name}</p>
            <p className="text-xs text-emerald-500 font-medium">● online</p>
          </div>
          <button
            onClick={handleLogout}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-all"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Chat area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {catchUpLoading && <CatchUpLoader />}
        {!catchUpLoading && catchUpData?.total_missed > 0 && (
          <CatchUpBanner
            data={catchUpData}
            onDismiss={() => setCatchUpData(null)}
            onNavigate={(groupId, groupName) => {
              setActiveConversation({ id: groupId, name: groupName, isGroup: true })
              setCatchUpData(null)
            }}
          />
        )}
        <div className="flex-1 flex overflow-hidden">
        <ChatWindow
          onRightTabChange={setRightTab}
          activeRightTab={rightTab}
          onInfoOpen={handleInfoOpen}
          onSharedOpen={handleSharedOpen}
        />
        </div>
      </main>

      {/* Right panel — always AI-focused */}
      <RightPanel
        onSearchOpen={() => setShowSearch(true)}
        onSettingsOpen={() => setShowSettings(true)}
        activeTab={rightTab}
        onTabChange={setRightTab}
      />

      {/* Modals */}
      {showSearch && <SearchModal onClose={() => setShowSearch(false)} />}
      {showGroupModal && <GroupModal onClose={() => setShowGroupModal(false)} />}
      {showSettings && <SettingsModal onClose={() => setShowSettings(false)} onSignOut={handleLogout} />}

      {infoUserId && (
        <UserInfoModal
          userId={infoUserId}
          onClose={() => setInfoUserId(null)}
          onMessage={() => {
            setActiveConversation({ id: infoUserId, name: '', isGroup: false })
            setInfoUserId(null)
          }}
        />
      )}

      {showSharedMedia && (
        <SharedMediaModal onClose={() => setShowSharedMedia(false)} />
      )}
    </div>
  )
}
