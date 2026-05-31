import { useState } from 'react'
import { X, Image, FileText, Mic, Video, File } from 'lucide-react'
import { useChatStore } from '../store/chatStore'
import { formatIST } from '../utils/time'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function resolveUrl(url) {
  if (!url) return ''
  return url.startsWith('http') ? url : `${API_BASE}${url}`
}

const TABS = [
  { key: 'all', label: 'All' },
  { key: 'image', label: 'Images' },
  { key: 'video', label: 'Videos' },
  { key: 'document', label: 'Documents' },
  { key: 'voice', label: 'Voice' },
]

function mediaTypeForTab(tab) {
  if (tab === 'all') return null
  if (tab === 'document') return ['document', 'file']
  return [tab]
}

export default function SharedMediaModal({ onClose }) {
  const { activeConversation, messages } = useChatStore()
  const [tab, setTab] = useState('all')

  const convId = activeConversation?.id
  const allMedia = (messages[convId] || []).filter((m) => m.media_type && m.media_type !== 'text' && !m.deleted)

  const types = mediaTypeForTab(tab)
  const filtered = types ? allMedia.filter((m) => types.includes(m.media_type)) : allMedia

  const countFor = (t) => {
    const ts = mediaTypeForTab(t)
    return ts ? allMedia.filter((m) => ts.includes(m.media_type)).length : allMedia.length
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-[540px] max-h-[80vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="px-5 py-4 flex items-center justify-between flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
        >
          <div>
            <h3 className="font-bold text-white text-sm">Shared Files</h3>
            <p className="text-white/60 text-xs">{activeConversation?.name}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-white/20 rounded-lg transition-all"
          >
            <X size={16} className="text-white" />
          </button>
        </div>

        {/* Type filter tabs */}
        <div className="flex px-4 pt-3 pb-0 gap-1 border-b border-slate-100 flex-shrink-0 overflow-x-auto">
          {TABS.map((t) => {
            const count = countFor(t.key)
            return (
              <button
                key={t.key}
                onClick={() => setTab(t.key)}
                className={`px-3 py-2 rounded-t-xl text-xs font-semibold whitespace-nowrap transition-all border-b-2 ${
                  tab === t.key
                    ? 'text-violet-600 border-violet-500 bg-violet-50/40'
                    : 'text-slate-500 border-transparent hover:text-slate-700 hover:bg-slate-50'
                }`}
              >
                {t.label} <span className="ml-1 text-slate-400 font-normal">({count})</span>
              </button>
            )
          })}
        </div>

        {/* Grid */}
        <div className="flex-1 overflow-y-auto p-4 scrollbar-thin">
          {filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-32 gap-2 text-slate-400">
              <File size={28} className="opacity-30" />
              <p className="text-sm">No files in this category</p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2.5">
              {filtered.map((msg) => (
                <MediaCard key={msg.message_id} msg={msg} />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MediaCard({ msg }) {
  const url = resolveUrl(msg.media_url)
  const ts = formatIST(msg.timestamp, 'dd MMM')

  if (msg.media_type === 'image') {
    return (
      <div
        className="relative rounded-xl overflow-hidden aspect-square cursor-pointer group shadow-sm border border-slate-100"
        onClick={() => url && window.open(url, '_blank')}
      >
        <img
          src={url}
          alt="shared"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
          onError={(e) => { e.currentTarget.style.display = 'none' }}
        />
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors" />
        <span className="absolute bottom-1.5 right-1.5 text-white text-xs bg-black/40 rounded-md px-1.5 py-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          {ts}
        </span>
      </div>
    )
  }

  if (msg.media_type === 'video') {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1.5 rounded-xl aspect-square cursor-pointer hover:opacity-80 transition-all border border-indigo-100 shadow-sm"
        style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}
        onClick={() => url && window.open(url, '_blank')}
      >
        <Video size={22} className="text-indigo-500" />
        <span className="text-xs text-indigo-600 font-semibold">Video</span>
        <span className="text-xs text-slate-400">{ts}</span>
      </div>
    )
  }

  if (msg.media_type === 'voice') {
    return (
      <div
        className="flex flex-col items-center justify-center gap-1.5 rounded-xl aspect-square border border-violet-100 shadow-sm p-2"
        style={{ background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)' }}
      >
        <Mic size={20} className="text-violet-500" />
        <span className="text-xs text-violet-600 font-semibold">Voice</span>
        {url && <audio src={url} controls style={{ height: '28px', width: '100%' }} />}
        <span className="text-xs text-slate-400">{ts}</span>
      </div>
    )
  }

  if (msg.media_type === 'document' || msg.media_type === 'file') {
    const ext = (msg.content || '').split('.').pop().toLowerCase()
    return (
      <div
        className="flex flex-col items-center justify-center gap-1.5 rounded-xl aspect-square cursor-pointer hover:opacity-80 transition-all border border-violet-100 shadow-sm p-2"
        style={{ background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)' }}
        onClick={() => url && window.open(url, '_blank')}
      >
        <FileText size={22} className="text-violet-500" />
        <span className="text-xs text-violet-600 font-semibold truncate w-full text-center px-1">
          {ext ? ext.toUpperCase() : 'Doc'}
        </span>
        <span className="text-xs text-slate-500 truncate w-full text-center px-1">{msg.content?.slice(0, 16)}</span>
        <span className="text-xs text-slate-400">{ts}</span>
      </div>
    )
  }

  return null
}
