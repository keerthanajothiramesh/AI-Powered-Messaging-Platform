import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, X, CheckCheck } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { formatISTFull } from '../utils/time'
import client from '../api/client'

export default function NotificationsDropdown() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const { notifications, setNotifications, markNotificationsRead } = useChatStore()
  const unread = notifications.filter((n) => !n.is_read).length

  // Load persisted notifications from API on mount and merge with any real-time ones
  useEffect(() => {
    client.get('/notifications/me')
      .then((r) => {
        const apiList = r.data.notifications || []
        useChatStore.setState((s) => {
          // Merge: API list is source of truth for persisted items; keep real-time-only ones on top
          const apiIds = new Set(apiList.map((n) => n.notification_id))
          const realtimeOnly = s.notifications.filter((n) => !apiIds.has(n.notification_id))
          return { notifications: [...realtimeOnly, ...apiList] }
        })
      })
      .catch(() => {})
  }, [])

  const handleMarkAllRead = async () => {
    markNotificationsRead()
    try { await client.put('/notifications/me/read') } catch {}
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-1.5 text-slate-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all"
      >
        <Bell size={16} />
        {unread > 0 && (
          <span
            className="absolute top-0.5 right-0.5 w-4 h-4 text-white text-xs rounded-full flex items-center justify-center font-bold"
            style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)', fontSize: '9px' }}
          >
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-2xl shadow-2xl border border-slate-100 z-50 overflow-hidden">
          <div
            className="flex items-center justify-between px-4 py-3 border-b border-slate-100"
            style={{ background: 'linear-gradient(135deg, #f0f4ff, #f5f3ff)' }}
          >
            <span className="font-semibold text-sm text-slate-800">{t('notifications.title')}</span>
            <div className="flex gap-2 items-center">
              {unread > 0 && (
                <button
                  onClick={handleMarkAllRead}
                  className="text-xs text-indigo-600 flex items-center gap-1 hover:text-indigo-800 font-medium"
                >
                  <CheckCheck size={12} /> {t('notifications.markAllRead')}
                </button>
              )}
              <button onClick={() => setOpen(false)} className="p-0.5 text-slate-400 hover:text-slate-600 rounded transition-colors">
                <X size={14} />
              </button>
            </div>
          </div>

          <div className="max-h-80 overflow-y-auto scrollbar-thin">
            {notifications.length === 0 ? (
              <p className="text-center text-sm text-slate-400 py-8">{t('notifications.noNotifications')}</p>
            ) : (
              notifications.map((n) => (
                <div
                  key={n.notification_id}
                  className={`px-4 py-3 border-b border-slate-50 transition-all ${
                    !n.is_read ? 'bg-indigo-50/50' : 'hover:bg-slate-50'
                  }`}
                >
                  <div className="flex justify-between items-start gap-2">
                    <p className="text-sm font-semibold text-slate-900">{n.title}</p>
                    {!n.is_read && (
                      <span
                        className="w-2 h-2 rounded-full flex-shrink-0 mt-1.5"
                        style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
                      />
                    )}
                  </div>
                  <p className="text-xs text-slate-600 mt-0.5">{n.body}</p>
                  <p className="text-xs text-slate-400 mt-1">{formatISTFull(n.created_at)}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
