import { useState } from 'react'
import { Sparkles, X, ChevronDown, ChevronUp, Loader2 } from 'lucide-react'

export default function CatchUpBanner({ data, onDismiss }) {
  const [expanded, setExpanded] = useState(false)

  if (!data || data.total_missed === 0) return null

  const groups = Object.entries(data.group_summaries || {})
  const dmCount = data.direct_messages?.count || 0
  const dmSummary = data.direct_messages?.summary

  return (
    <div
      className="flex-shrink-0 mx-3 mt-2 mb-0 rounded-xl border border-indigo-200 overflow-hidden shadow-sm"
      style={{ background: 'linear-gradient(135deg, #eef2ff, #f5f3ff)' }}
    >
      {/* Header row */}
      <div className="flex items-center gap-2.5 px-4 py-2.5">
        <div
          className="w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
        >
          <Sparkles size={13} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-indigo-700 leading-tight">
            You missed {data.total_missed} message{data.total_missed !== 1 ? 's' : ''}
          </p>
          <p className="text-xs text-slate-500 leading-tight truncate">
            AI catch-up summary ready
          </p>
        </div>
        <button
          onClick={() => setExpanded((v) => !v)}
          className="p-1 text-indigo-400 hover:text-indigo-600 rounded-lg hover:bg-indigo-100 transition-all"
        >
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </button>
        <button
          onClick={onDismiss}
          className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-all"
        >
          <X size={15} />
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="px-4 pb-3 space-y-2 border-t border-indigo-100 pt-2.5 max-h-52 overflow-y-auto scrollbar-thin">
          {dmCount > 0 && dmSummary && (
            <SummaryCard label="Direct messages" count={dmCount} summary={dmSummary} color="violet" />
          )}
          {groups.map(([name, info]) => (
            <SummaryCard key={name} label={name} count={info.count} summary={info.summary} color="indigo" />
          ))}
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, count, summary, color }) {
  const colors = {
    indigo: 'bg-indigo-50 border-indigo-100 text-indigo-700',
    violet: 'bg-violet-50 border-violet-100 text-violet-700',
  }
  return (
    <div className={`rounded-lg border p-2.5 ${colors[color]}`}>
      <p className="text-xs font-semibold mb-1">
        {label} <span className="font-normal opacity-60">· {count} new</span>
      </p>
      <p className="text-xs text-slate-600 leading-relaxed">{summary}</p>
    </div>
  )
}

export function CatchUpLoader() {
  return (
    <div
      className="flex-shrink-0 mx-3 mt-2 mb-0 rounded-xl border border-indigo-100 px-4 py-2.5 flex items-center gap-2.5"
      style={{ background: 'linear-gradient(135deg, #eef2ff, #f5f3ff)' }}
    >
      <Loader2 size={13} className="text-indigo-400 animate-spin flex-shrink-0" />
      <p className="text-xs text-indigo-500 font-medium">Generating catch-up summary…</p>
    </div>
  )
}
