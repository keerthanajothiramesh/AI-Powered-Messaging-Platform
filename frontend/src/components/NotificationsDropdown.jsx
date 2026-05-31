import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { Bell, X, CheckCheck } from 'lucide-react'
import { format } from 'date-fns'
import client from '../api/client'

export default function NotificationsDropdown() {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] = useState([])
  const unread = notifications.filter((n) => !n.is_read).length

  useEffect(() => {
    client.get('/notifications/me').then((r) => setNotifications(r.data.notifications || [])).catch(() => {})
  }, [])

  const markAllRead = async () => {
    await client.put('/notifications/me/read')
    setNotifications((ns) => ns.map((n) => ({ ...n, is_read: true })))
  }

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
      >
        <Bell size={20} />
        {unread > 0 && (
          <span className="absolute top-1 right-1 w-4 h-4 bg-primary text-white text-xs rounded-full flex items-center justify-center">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-80 bg-white rounded-xl shadow-xl border border-gray-100 z-50">
          <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
            <span className="font-semibold text-sm">{t('notifications.title')}</span>
            <div className="flex gap-2">
              {unread > 0 && (
                <button onClick={markAllRead} className="text-xs text-primary flex items-center gap-1">
                  <CheckCheck size={12} /> {t('notifications.markAllRead')}
                </button>
              )}
              <button onClick={() => setOpen(false)}><X size={14} /></button>
            </div>
          </div>
          <div className="max-h-80 overflow-y-auto scrollbar-thin">
            {notifications.length === 0
              ? <p className="text-center text-sm text-gray-400 py-6">{t('notifications.noNotifications')}</p>
              : notifications.map((n) => (
                  <div key={n.notification_id} className={`px-4 py-3 border-b border-gray-50 ${!n.is_read ? 'bg-red-50/30' : ''}`}>
                    <div className="flex justify-between items-start">
                      <p className="text-sm font-medium text-gray-900">{n.title}</p>
                      {!n.is_read && <span className="w-2 h-2 bg-primary rounded-full flex-shrink-0 mt-1" />}
                    </div>
                    <p className="text-xs text-gray-600 mt-0.5">{n.body}</p>
                    <p className="text-xs text-gray-400 mt-1">
                      {n.created_at ? format(new Date(n.created_at), 'MMM d, HH:mm') : ''}
                    </p>
                  </div>
                ))
            }
          </div>
        </div>
      )}
    </div>
  )
}
