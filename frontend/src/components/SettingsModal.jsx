import { useState } from 'react'
import { X, User, Briefcase, Building2, MapPin, Layers } from 'lucide-react'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
import toast from 'react-hot-toast'

const PRESENCE_OPTIONS = [
  { label: 'Available',      value: 'online',   dot: 'bg-emerald-500' },
  { label: 'Busy',           value: 'away',     dot: 'bg-red-500' },
  { label: 'Do not disturb', value: 'away',     dot: 'bg-red-600' },
  { label: 'Be right back',  value: 'away',     dot: 'bg-amber-400' },
  { label: 'Appear away',    value: 'away',     dot: 'bg-amber-400' },
  { label: 'Appear offline', value: 'offline',  dot: 'bg-slate-400' },
]

const presenceToLabel = { online: 'Available', away: 'Appear away', offline: 'Appear offline' }

const TABS = ['Status', 'Profile']

export default function SettingsModal({ onClose, onSignOut }) {
  const { user } = useAuthStore()
  const [tab, setTab] = useState('Status')
  const [selected, setSelected] = useState(presenceToLabel[user?.user_presence] || 'Available')

  // Profile fields
  const [jobTitle, setJobTitle] = useState(user?.job_title || '')
  const [company, setCompany] = useState(user?.company || '')
  const [department, setDepartment] = useState(user?.department || '')
  const [workLocation, setWorkLocation] = useState(user?.work_location || '')
  const [saving, setSaving] = useState(false)

  const handlePresenceSelect = async (opt) => {
    setSelected(opt.label)
    try {
      await client.put(`/users/me/status?status=${opt.value}`)
      toast.success('Status updated')
    } catch {
      toast.error('Failed to update status')
    }
  }

  const handleProfileSave = async () => {
    setSaving(true)
    try {
      await client.put('/users/me/profile', {
        job_title: jobTitle || null,
        company: company || null,
        department: department || null,
        work_location: workLocation || null,
      })
      toast.success('Profile saved')
    } catch {
      toast.error('Failed to save profile')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-80 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div
          className="px-4 py-4 flex items-center justify-between"
          style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
        >
          <p className="text-sm font-semibold text-white">Settings</p>
          <button
            onClick={onClose}
            className="p-1 text-white/60 hover:text-white rounded-lg hover:bg-white/15 transition-all"
          >
            <X size={15} />
          </button>
        </div>

        {/* Profile summary */}
        <div className="px-5 py-4 border-b border-slate-100 flex items-center gap-4">
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

        {/* Inner tabs */}
        <div className="flex border-b border-slate-100 text-xs font-semibold">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 py-2.5 transition-all ${
                tab === t
                  ? 'text-violet-600 border-b-2 border-violet-500 bg-violet-50/30'
                  : 'text-slate-500 hover:text-slate-700'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === 'Status' ? (
          <div className="py-1 max-h-64 overflow-y-auto">
            {PRESENCE_OPTIONS.map((opt) => (
              <button
                key={opt.label}
                onClick={() => handlePresenceSelect(opt)}
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
        ) : (
          <div className="px-4 py-4 space-y-3">
            <ProfileField
              icon={<Briefcase size={13} className="text-violet-400" />}
              label="Job title"
              value={jobTitle}
              onChange={setJobTitle}
              placeholder="e.g. Software Engineer"
            />
            <ProfileField
              icon={<Layers size={13} className="text-blue-400" />}
              label="Department"
              value={department}
              onChange={setDepartment}
              placeholder="e.g. AI and Data"
            />
            <ProfileField
              icon={<Building2 size={13} className="text-sky-400" />}
              label="Company"
              value={company}
              onChange={setCompany}
              placeholder="e.g. Prodapt Solutions"
            />
            <ProfileField
              icon={<MapPin size={13} className="text-emerald-400" />}
              label="Work location"
              value={workLocation}
              onChange={setWorkLocation}
              placeholder="e.g. Chennai - Guindy"
            />
            <button
              onClick={handleProfileSave}
              disabled={saving}
              className="w-full py-2 text-sm text-white font-semibold rounded-xl mt-2 disabled:opacity-50 transition-all"
              style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
            >
              {saving ? 'Saving…' : 'Save Profile'}
            </button>
          </div>
        )}

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

function ProfileField({ icon, label, value, onChange, placeholder }) {
  return (
    <div>
      <label className="flex items-center gap-1.5 text-xs text-slate-500 font-semibold mb-1">
        {icon} {label}
      </label>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-violet-300 focus:border-violet-300 transition-all"
      />
    </div>
  )
}
