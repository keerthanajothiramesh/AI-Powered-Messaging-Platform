import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Users, Loader2, Sparkles, Image, Mic, Video } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import client from '../api/client'
import toast from 'react-hot-toast'

export default function RightPanel() {
  const { t } = useTranslation()
  const { activeConversation } = useChatStore()
  const [members, setMembers] = useState([])
  const [summary, setSummary] = useState(null)
  const [summarising, setSummarising] = useState(false)
  const [media, setMedia] = useState([])
  const [mediaTab, setMediaTab] = useState('all')

  useEffect(() => {
    if (!activeConversation?.isGroup) { setMembers([]); return }
    client.get(`/groups/${activeConversation.id}`)
      .then((r) => setMembers(r.data.members || []))
      .catch(() => {})
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

  if (!activeConversation) return null

  return (
    <div className="w-60 flex flex-col bg-white border-l border-gray-100">
      {activeConversation.isGroup ? (
        <>
          <div className="px-4 py-4 border-b border-gray-100">
            <h3 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
              <Users size={16} /> {t('chat.members')} ({members.length})
            </h3>
          </div>
          <div className="flex-1 overflow-y-auto scrollbar-thin">
            {members.map((m) => (
              <div key={m.user_id} className="flex items-center gap-2 px-4 py-2">
                <div className="relative">
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
          <div className="p-3 border-t border-gray-100">
            <button
              onClick={handleSummary}
              disabled={summarising}
              className="w-full flex items-center justify-center gap-2 py-2 bg-primary/10 text-primary rounded-lg text-sm font-medium hover:bg-primary/20 disabled:opacity-60 transition-colors"
            >
              {summarising ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {t('groups.aiSummary')}
            </button>
            {summary && (
              <div className="mt-2 p-2 bg-gray-50 rounded-lg text-xs text-gray-700 leading-relaxed max-h-40 overflow-y-auto scrollbar-thin">
                {summary}
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="p-4 text-center text-sm text-gray-500">
          <p>Direct conversation</p>
        </div>
      )}
    </div>
  )
}
