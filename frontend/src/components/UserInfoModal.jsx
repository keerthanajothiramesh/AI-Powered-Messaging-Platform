import { useEffect, useState } from 'react'
import { X, Mail, Briefcase, Building2, MapPin, Layers, MessageCircle, Loader2 } from 'lucide-react'
import { formatIST, isISTToday, isISTYesterday } from '../utils/time'
import client from '../api/client'

function formatLastSeen(ts) {
  if (!ts) return null
  if (isISTToday(ts)) return `Today at ${formatIST(ts)}`
  if (isISTYesterday(ts)) return `Yesterday at ${formatIST(ts)}`
  return formatIST(ts, 'dd MMM yyyy')
}

export default function UserInfoModal({ userId, onClose, onMessage }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!userId) return
    setLoading(true)
    client.get(`/users/${userId}`)
      .then((r) => setUser(r.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [userId])

  const isOnline = user?.user_presence === 'online'
  const lastSeenLabel = formatLastSeen(user?.last_seen)
  const presenceText = isOnline ? 'Online' : lastSeenLabel ? `Last seen ${lastSeenLabel}` : 'Offline'

  return (
    <div
      className="fixed inset-0 bg-black/30 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-80 overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Gradient banner */}
        <div
          className="h-20 relative flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #6366f1 0%, #7c3aed 60%, #a855f7 100%)' }}
        >
          <button
            onClick={onClose}
            className="absolute top-3 right-3 p-1.5 hover:bg-white/20 rounded-lg transition-all"
          >
            <X size={15} className="text-white" />
          </button>
        </div>

        {loading ? (
          <div className="flex items-center justify-center h-40">
            <Loader2 size={22} className="animate-spin text-indigo-400" />
          </div>
        ) : user ? (
          <div className="px-5 pb-5">
            {/* Avatar overlapping banner, name/status below in white area */}
            <div className="-mt-8 mb-4">
              <div
                className="w-16 h-16 rounded-2xl flex items-center justify-center text-white text-xl font-bold shadow-xl border-4 border-white mb-2"
                style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
              >
                {user.display_name?.slice(0, 2).toUpperCase() || '??'}
              </div>
              <h3 className="font-bold text-slate-900 text-base leading-tight">{user.display_name}</h3>
              <p className={`text-xs font-semibold mt-0.5 ${isOnline ? 'text-emerald-500' : 'text-slate-400'}`}>
                ● {presenceText}
              </p>
            </div>

            {/* Divider */}
            <div className="border-t border-slate-100 mb-4" />

            {/* Contact info */}
            <p className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-3">Contact information</p>
            <div className="space-y-3 mb-5">
              {user.email && (
                <InfoRow icon={<Mail size={13} className="text-indigo-400" />} label="Email" value={user.email} color="bg-indigo-50" />
              )}
              {user.job_title && (
                <InfoRow icon={<Briefcase size={13} className="text-violet-400" />} label="Job title" value={user.job_title} color="bg-violet-50" />
              )}
              {user.department && (
                <InfoRow icon={<Layers size={13} className="text-blue-400" />} label="Department" value={user.department} color="bg-blue-50" />
              )}
              {user.company && (
                <InfoRow icon={<Building2 size={13} className="text-sky-400" />} label="Company" value={user.company} color="bg-sky-50" />
              )}
              {user.work_location && (
                <InfoRow icon={<MapPin size={13} className="text-emerald-400" />} label="Work location" value={user.work_location} color="bg-emerald-50" />
              )}
              {!user.email && !user.job_title && !user.company && !user.work_location && (
                <p className="text-xs text-slate-400 italic">No contact info available</p>
              )}
            </div>

            {/* Send message button */}
            {onMessage && (
              <button
                onClick={() => { onMessage(); onClose() }}
                className="w-full py-2.5 text-sm text-white font-semibold rounded-xl flex items-center justify-center gap-2 transition-all hover:opacity-90 shadow-md"
                style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
              >
                <MessageCircle size={15} /> Send Message
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-40">
            <p className="text-sm text-slate-400">Unable to load profile</p>
          </div>
        )}
      </div>
    </div>
  )
}

function InfoRow({ icon, label, value, color }) {
  return (
    <div className="flex items-start gap-3">
      <div className={`w-7 h-7 rounded-lg ${color} flex items-center justify-center flex-shrink-0 mt-0.5`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-400 font-medium">{label}</p>
        <p className="text-xs text-slate-800 font-semibold break-all">{value}</p>
      </div>
    </div>
  )
}
