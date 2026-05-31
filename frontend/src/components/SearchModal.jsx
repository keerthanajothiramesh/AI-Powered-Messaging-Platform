import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Search, Loader2, Sparkles } from 'lucide-react'
import { format } from 'date-fns'
import client from '../api/client'

export default function SearchModal({ onClose }) {
  const { t } = useTranslation()
  const [query, setQuery] = useState('')
  const [aiMode, setAiMode] = useState(false)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSearch = async () => {
    if (!query.trim()) return
    setLoading(true)
    try {
      if (aiMode) {
        const r = await client.post('/ai/search', { query })
        setResults({ type: 'ai', answer: r.data.answer, sources: r.data.sources })
      } else {
        const r = await client.post('/search', { query, n_results: 20 })
        setResults({ type: 'keyword', items: r.data.results })
      }
    } catch { setResults({ type: 'error' }) } finally { setLoading(false) }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-16 px-4"
      style={{ background: 'rgba(30, 27, 75, 0.55)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden border border-indigo-100" onClick={(e) => e.stopPropagation()}>
        {/* Search bar */}
        <div className="p-4 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <Search size={20} className="text-indigo-400 flex-shrink-0" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={t('search.placeholder')}
              className="flex-1 text-lg focus:outline-none text-slate-800 placeholder:text-slate-300"
            />
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500">AI</span>
              <button
                onClick={() => setAiMode(!aiMode)}
                className="w-10 h-5 rounded-full transition-all relative"
                style={{ background: aiMode ? 'linear-gradient(135deg, #6366f1, #7c3aed)' : '#cbd5e1' }}
              >
                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${aiMode ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-slate-100 rounded-lg transition-all">
              <X size={18} className="text-slate-500" />
            </button>
          </div>
          <div className="mt-2.5 flex gap-2">
            <span className={`text-xs px-2.5 py-1 rounded-full font-semibold transition-all ${
              !aiMode ? 'text-white' : 'bg-slate-100 text-slate-500'
            }`}
            style={!aiMode ? { background: 'linear-gradient(135deg, #6366f1, #7c3aed)' } : {}}>
              {t('search.keyword')}
            </span>
            <span className={`text-xs px-2.5 py-1 rounded-full font-semibold transition-all flex items-center gap-1 ${
              aiMode ? 'text-white' : 'bg-slate-100 text-slate-500'
            }`}
            style={aiMode ? { background: 'linear-gradient(135deg, #6366f1, #7c3aed)' } : {}}>
              {aiMode && <Sparkles size={10} />}
              {t('search.aiSearch')}
            </span>
          </div>
        </div>

        <div className="max-h-96 overflow-y-auto scrollbar-thin">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-10 text-indigo-400">
              <Loader2 size={20} className="animate-spin" />
              <span className="text-sm font-medium">{t('search.searching')}</span>
            </div>
          )}

          {results?.type === 'ai' && (
            <div className="p-4">
              <div className="rounded-2xl p-4 mb-4 border border-indigo-100"
                   style={{ background: 'linear-gradient(135deg, #eef2ff, #f5f3ff)' }}>
                <p className="text-sm font-semibold text-indigo-700 mb-1.5 flex items-center gap-1.5">
                  <Sparkles size={14} /> AI Answer
                </p>
                <p className="text-sm text-slate-700 leading-relaxed">{results.answer}</p>
              </div>
              {results.sources?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-slate-500 mb-2">Sources ({results.sources.length})</p>
                  {results.sources.map((r, i) => <ResultCard key={i} result={r} query={query} />)}
                </div>
              )}
            </div>
          )}

          {results?.type === 'keyword' && (
            <div className="p-4">
              <p className="text-xs text-slate-500 mb-3 font-medium">{results.items?.length} {t('search.results')}</p>
              {results.items?.length === 0
                ? <p className="text-center text-slate-400 py-6">{t('search.noResults')}</p>
                : results.items.map((r, i) => <ResultCard key={i} result={r} query={query} />)
              }
            </div>
          )}

          {!results && !loading && (
            <div className="py-14 text-center">
              <Search size={36} className="mx-auto mb-3 text-indigo-200" />
              <p className="text-sm text-slate-400">Press Enter or type to search</p>
            </div>
          )}

          {results?.type === 'error' && (
            <div className="py-10 text-center text-red-400 text-sm">Search failed. Please try again.</div>
          )}
        </div>
      </div>
    </div>
  )
}

function ResultCard({ result, query }) {
  const content = result.content || ''
  const highlighted = content.replace(
    new RegExp(`(${query.split(' ').filter(Boolean).join('|')})`, 'gi'),
    '<mark class="bg-yellow-200 rounded px-0.5">$1</mark>'
  )
  const meta = result.metadata || {}
  const ts = meta.timestamp ? format(new Date(meta.timestamp), 'MMM d, HH:mm') : ''

  return (
    <div className="border border-slate-100 rounded-xl p-3 mb-2 hover:bg-indigo-50/30 hover:border-indigo-100 transition-all shadow-sm">
      <p className="text-sm text-slate-800 leading-relaxed" dangerouslySetInnerHTML={{ __html: highlighted }} />
      <div className="flex gap-3 mt-2 text-xs text-slate-400">
        {ts && <span>{ts}</span>}
        {meta.media_type && meta.media_type !== 'text' && (
          <span className="capitalize bg-indigo-50 text-indigo-500 px-1.5 py-0.5 rounded-full font-medium">{meta.media_type}</span>
        )}
      </div>
    </div>
  )
}
