import { useState } from 'react'
import { X } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
import toast from 'react-hot-toast'

const PRESENCE_OPTIONS = [
  { label: 'Available',      value: 'online',   dot: 'bg-emerald-500', check: '✓' },
  { label: 'Busy',           value: 'away',     dot: 'bg-red-500',     check: '—' },
  { label: 'Do not disturb', value: 'away',     dot: 'bg-red-600',     check: '⊘' },
  { label: 'Be right back',  value: 'away',     dot: 'bg-amber-400',   check: '↩' },
  { label: 'Appear away',    value: 'away',     dot: 'bg-amber-400',   check: '○' },
  { label: 'Appear offline', value: 'offline',  dot: 'bg-slate-400',   check: '●' },
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
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-76 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header gradient */}
        <div className="px-4 py-4 flex items-center justify-between"
             style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}>
          <p className="text-sm font-semibold text-white">Settings</p>
          <button
            onClick={onClose}
            className="p-1 text-white/60 hover:text-white rounded-lg hover:bg-white/15 transition-all"
          >
            <X size={15} />
          </button>
        </div>

        {/* Profile */}
        <div className="px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-4">
            <div
              className="w-14 h-14 rounded-2xl flex items-center justify-center text-white text-xl font-bold shadow-lg flex-shrink-0"
              style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
            >
              {user?.display_name?.slice(0, 2).toUpperCase() || 'U'}
            </div>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-900 truncate">{user?.display_name}</p>
              <p className="text-xs text-slate-400 truncate mt-0.5">{user?.email}</p>
            </div>
          </div>
        </div>

        {/* Presence options */}
        <div className="py-1">
          <p className="px-4 pt-2 pb-1 text-xs font-semibold text-slate-400 uppercase tracking-wider">Status</p>
          {PRESENCE_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              onClick={() => handleSelect(opt)}
              className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-indigo-50 text-left transition-all"
            >
              <span className={`w-3 h-3 rounded-full flex-shrink-0 ${opt.dot}`} />
              <span className="text-sm text-slate-700 flex-1">{opt.label}</span>
              {selected === opt.label && (
                <span className="text-xs text-indigo-600 font-bold">✓</span>
              )}
            </button>
          ))}
        </div>

        <div className="px-4 py-3 border-t border-slate-100">
          <button
            onClick={onSignOut}
            className="w-full text-sm text-red-500 hover:text-red-600 font-semibold py-2 rounded-xl hover:bg-red-50 transition-all"
          >
            Sign out
          </button>
        </div>
      </div>
    </div>
  )
}
