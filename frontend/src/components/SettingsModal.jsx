import { useState, useEffect } from 'react'
import { X, User, Briefcase, Building2, MapPin, Layers, Database, Loader2, CheckCircle2, AlertCircle, Trash2 } from 'lucide-react'
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

const TABS = ['Status', 'Profile', 'Demo']

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

  // Fetch saved profile fields from API when Profile tab opens
  useEffect(() => {
    if (tab !== 'Profile') return
    client.get(`/users/${user?.user_id}`).then(r => {
      const u = r.data
      setJobTitle(u.job_title || 'Software Engineer')
      setDepartment(u.department || 'Delivery')
      setWorkLocation(u.work_location || 'Chennai - Guindy')
      setCompany(u.company || '')
    }).catch(() => {})
  }, [tab])

  // Demo dataset state
  const [seedStatus, setSeedStatus] = useState(null)
  const [confirmRemove, setConfirmRemove] = useState(false)
  const [realMsgCount, setRealMsgCount] = useState(0)

  // Fetch status whenever the Demo tab is opened
  useEffect(() => {
    if (tab !== 'Demo') return
    client.get('/admin/seed-status').then(r => setSeedStatus(r.data)).catch(() => {})
  }, [tab])

  // Poll while running or removing
  useEffect(() => {
    const active = seedStatus?.status === 'running' || seedStatus?.status === 'removing'
    if (!active) return
    const id = setInterval(() => {
      client.get('/admin/seed-status').then(r => setSeedStatus(r.data)).catch(() => {})
    }, 1500)
    return () => clearInterval(id)
  }, [seedStatus?.status])

  const handleLoadDemo = async () => {
    try {
      await client.post('/admin/seed-demo')
      setSeedStatus(s => ({ ...s, status: 'running', step: 'Starting…' }))
    } catch {
      toast.error('Failed to start seeding')
    }
  }

  const handleRemoveClick = async () => {
    try {
      const { data } = await client.get('/admin/seed-demo/real-count')
      setRealMsgCount(data.count || 0)
      setConfirmRemove(true)
    } catch {
      setConfirmRemove(true)
    }
  }

  const handleConfirmRemove = async () => {
    setConfirmRemove(false)
    try {
      await client.delete('/admin/seed-demo')
      setSeedStatus(s => ({ ...s, status: 'removing', step: 'Starting removal…' }))
    } catch {
      toast.error('Failed to start removal')
    }
  }

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

        {tab === 'Status' && (
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
        )}

        {tab === 'Profile' && (
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

        {tab === 'Demo' && (
          <div className="px-4 py-4 space-y-3">
            <DemoTab
              status={seedStatus}
              confirmRemove={confirmRemove}
              realMsgCount={realMsgCount}
              onLoad={handleLoadDemo}
              onRemoveClick={handleRemoveClick}
              onConfirmRemove={handleConfirmRemove}
              onCancelRemove={() => setConfirmRemove(false)}
            />
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

// ─── DemoTab component ────────────────────────────────────────────────────────

function DemoTab({ status, confirmRemove, realMsgCount, onLoad, onRemoveClick, onConfirmRemove, onCancelRemove }) {
  if (!status) {
    return (
      <div className="flex items-center justify-center py-6">
        <Loader2 size={18} className="animate-spin text-indigo-400" />
      </div>
    )
  }

  if (confirmRemove) {
    return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 bg-amber-50 border border-amber-200 rounded-xl p-3">
          <AlertCircle size={15} className="text-amber-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs font-semibold text-amber-700">Remove demo data?</p>
            {realMsgCount > 0 && (
              <p className="text-xs text-amber-600 mt-0.5">
                You have {realMsgCount} real message{realMsgCount !== 1 ? 's' : ''} inside demo groups — they will also be deleted.
              </p>
            )}
            <p className="text-xs text-amber-600 mt-0.5">All 150 users, 25 groups, and 60,000 messages will be removed.</p>
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={onCancelRemove}
            className="flex-1 py-2 text-xs font-semibold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all"
          >
            Cancel
          </button>
          <button
            onClick={onConfirmRemove}
            className="flex-1 py-2 text-xs font-semibold text-white bg-red-500 hover:bg-red-600 rounded-xl transition-all"
          >
            Remove
          </button>
        </div>
      </div>
    )
  }

  if (status.status === 'error') {
    return (
      <div className="space-y-3">
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 rounded-xl p-3">
          <AlertCircle size={15} className="text-red-500 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-xs font-semibold text-red-700">Something went wrong</p>
            <p className="text-xs text-red-600 mt-0.5 break-all">{status.error}</p>
          </div>
        </div>
        <button
          onClick={onLoad}
          className="w-full py-2 text-xs font-semibold text-white rounded-xl transition-all"
          style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
        >
          Retry
        </button>
      </div>
    )
  }

  if (status.status === 'running' || status.status === 'removing') {
    const isRemoving = status.status === 'removing'
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Loader2 size={14} className="animate-spin text-indigo-500 flex-shrink-0" />
          <p className="text-xs font-semibold text-indigo-600">
            {isRemoving ? 'Removing demo data…' : 'Loading demo dataset…'}
          </p>
        </div>
        <p className="text-xs text-slate-400">{status.step}</p>
        {!isRemoving && (
          <div className="space-y-2">
            <ProgressBar label="Users" loaded={status.users_loaded} total={status.users_total} color="violet" />
            <ProgressBar label="Groups" loaded={status.groups_loaded} total={status.groups_total} color="blue" />
            <ProgressBar label="Messages" loaded={status.messages_loaded} total={status.messages_total} color="indigo" />
            <ProgressBar label="Embeddings" loaded={status.embeddings_loaded} total={status.embeddings_total} color="purple" />
          </div>
        )}
      </div>
    )
  }

  if (status.status === 'done') {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 bg-emerald-50 border border-emerald-200 rounded-xl p-3">
          <CheckCircle2 size={15} className="text-emerald-500 flex-shrink-0" />
          <div>
            <p className="text-xs font-semibold text-emerald-700">Demo data active</p>
            <p className="text-xs text-emerald-600 mt-0.5">150 users · 25 groups · 60,000 messages loaded. You've been added to all groups.</p>
          </div>
        </div>
        <div className="bg-slate-50 rounded-xl p-3 space-y-1">
          <p className="text-xs font-semibold text-slate-600">Try these queries in the AI assistant:</p>
          {[
            'Find Priya\'s message about the project deadline',
            'Summarise the project-launch group',
            'Show me renovation images from team chat',
          ].map((q) => (
            <p key={q} className="text-xs text-indigo-600 font-medium">"{q}"</p>
          ))}
        </div>
        <button
          onClick={onRemoveClick}
          className="w-full flex items-center justify-center gap-1.5 py-2 text-xs font-semibold text-red-500 border border-red-200 hover:bg-red-50 rounded-xl transition-all"
        >
          <Trash2 size={12} /> Remove Demo Data
        </button>
      </div>
    )
  }

  // idle — not yet loaded
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2.5">
        <div
          className="w-8 h-8 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
        >
          <Database size={14} className="text-white" />
        </div>
        <div>
          <p className="text-xs font-semibold text-slate-800">Synthetic Demo Dataset</p>
          <p className="text-xs text-slate-500 mt-0.5">150 users · 25 groups · 60,000 messages</p>
          <p className="text-xs text-slate-400 mt-0.5">English + Japanese, real-world chat patterns</p>
        </div>
      </div>
      <p className="text-xs text-slate-500 leading-relaxed">
        Loads the full synthetic dataset into the system and adds you to all demo groups — so you can test AI queries against realistic data.
      </p>
      <p className="text-xs text-amber-600 bg-amber-50 border border-amber-100 rounded-lg px-2.5 py-1.5">
        ⏳ Embedding generation takes 2–5 minutes after messages load.
      </p>
      <button
        onClick={onLoad}
        className="w-full py-2 text-sm font-semibold text-white rounded-xl transition-all shadow-sm"
        style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
      >
        Load Demo Dataset
      </button>
    </div>
  )
}

function ProgressBar({ label, loaded, total, color }) {
  const pct = total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0
  const colors = {
    violet: 'bg-violet-500',
    blue: 'bg-blue-500',
    indigo: 'bg-indigo-500',
    purple: 'bg-purple-500',
  }
  return (
    <div>
      <div className="flex justify-between text-xs text-slate-500 mb-0.5">
        <span>{label}</span>
        <span>{total > 0 ? `${loaded.toLocaleString()} / ${total.toLocaleString()}` : '—'}</span>
      </div>
      <div className="h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ${colors[color]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────

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
