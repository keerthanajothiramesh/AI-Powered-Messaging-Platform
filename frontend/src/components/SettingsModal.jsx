import { useState } from 'react'
import { X } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
import toast from 'react-hot-toast'

const PRESENCE_OPTIONS = [
  { label: 'Available',      value: 'online',   dot: 'bg-green-500',  check: '✓' },
  { label: 'Busy',           value: 'away',     dot: 'bg-red-500',    check: '—' },
  { label: 'Do not disturb', value: 'away',     dot: 'bg-red-600',    check: '⊘' },
  { label: 'Be right back',  value: 'away',     dot: 'bg-yellow-400', check: '↩' },
  { label: 'Appear away',    value: 'away',     dot: 'bg-yellow-400', check: '○' },
  { label: 'Appear offline', value: 'offline',  dot: 'bg-gray-400',   check: '●' },
]

const presenceToLabel = { online: 'Available', away: 'Appear away', offline: 'Appear offline' }

export default function SettingsModal({ onClose, onSignOut }) {
  const { user } = useAuthStore()
  const [selected, setSelected] = useState(presenceToLabel[user?.user_presence] || 'Available')

  const handleSelect = async (opt) => {
    setSelected(opt.label)
    try {
      await client.put(`/users/me/status?status=${opt.value}`)
      toast.success('Status updated')
    } catch {
      toast.error('Failed to update status')
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-72 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <p className="text-sm font-semibold text-gray-700">Settings</p>
          <button onClick={onClose} className="p-1 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100 transition-colors">
            <X size={15} />
          </button>
        </div>

        <div className="px-4 py-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center text-white text-lg font-semibold flex-shrink-0">
              {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-gray-900 truncate">{user?.display_name}</p>
              <p className="text-xs text-gray-500 truncate">{user?.email}</p>
            </div>
          </div>
        </div>

        <div className="py-1">
          {PRESENCE_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              onClick={() => handleSelect(opt)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-gray-50 text-left transition-colors"
            >
              <span className={`w-3 h-3 rounded-full flex-shrink-0 ${opt.dot}`} />
              <span className="text-sm text-gray-700 flex-1">{opt.label}</span>
              {selected === opt.label && (
                <span className="text-xs text-primary font-bold">✓</span>
              )}
            </button>
          ))}
        </div>

        <div className="px-4 py-3 border-t border-gray-100">
          <button
            onClick={onSignOut}
            className="w-full text-sm text-red-500 hover:text-red-600 font-medium py-1 transition-colors"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}
