import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Search, Loader2, ToggleLeft, ToggleRight } from 'lucide-react'
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
    <div className="fixed inset-0 bg-black/40 z-50 flex items-start justify-center pt-16 px-4" onClick={onClose}>
      <div className="w-full max-w-2xl bg-white rounded-2xl shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center gap-3">
            <Search size={20} className="text-gray-400 flex-shrink-0" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder={t('search.placeholder')}
              className="flex-1 text-lg focus:outline-none"
            />
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500">AI</span>
              <button
                onClick={() => setAiMode(!aiMode)}
                className={`w-10 h-5 rounded-full transition-colors ${aiMode ? 'bg-primary' : 'bg-gray-300'} relative`}
              >
                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${aiMode ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </button>
            </div>
            <button onClick={onClose} className="p-1 hover:bg-gray-100 rounded-lg">
              <X size={18} />
            </button>
          </div>
          <div className="mt-2 flex gap-2">
            <span className={`text-xs px-2 py-1 rounded-full ${!aiMode ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}>
              {t('search.keyword')}
            </span>
            <span className={`text-xs px-2 py-1 rounded-full ${aiMode ? 'bg-primary text-white' : 'bg-gray-100 text-gray-600'}`}>
              {t('search.aiSearch')}
            </span>
          </div>
        </div>

        <div className="max-h-96 overflow-y-auto scrollbar-thin">
          {loading && (
            <div className="flex items-center justify-center gap-2 py-8 text-gray-400">
              <Loader2 size={20} className="animate-spin" />
              {t('search.searching')}
            </div>
          )}

          {results?.type === 'ai' && (
            <div className="p-4">
              <div className="bg-red-50 border border-red-100 rounded-xl p-4 mb-4">
                <p className="text-sm font-medium text-primary mb-1">AI Answer</p>
                <p className="text-sm text-gray-700">{results.answer}</p>
              </div>
              {results.sources?.length > 0 && (
                <div>
                  <p className="text-xs font-medium text-gray-500 mb-2">Sources ({results.sources.length})</p>
                  {results.sources.map((r, i) => <ResultCard key={i} result={r} query={query} />)}
                </div>
              )}
            </div>
          )}

          {results?.type === 'keyword' && (
            <div className="p-4">
              <p className="text-xs text-gray-500 mb-2">{results.items?.length} {t('search.results')}</p>
              {results.items?.length === 0
                ? <p className="text-center text-gray-400 py-4">{t('search.noResults')}</p>
                : results.items.map((r, i) => <ResultCard key={i} result={r} query={query} />)
              }
            </div>
          )}

          {!results && !loading && (
            <div className="py-12 text-center text-gray-400 text-sm">
              <Search size={32} className="mx-auto mb-2 opacity-30" />
              Press Enter or type to search
            </div>
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
    '<mark class="bg-yellow-200 rounded">$1</mark>'
  )
  const meta = result.metadata || {}
  const ts = meta.timestamp ? format(new Date(meta.timestamp), 'MMM d, HH:mm') : ''

  return (
    <div className="border border-gray-100 rounded-xl p-3 mb-2 hover:bg-gray-50 transition-colors">
      <p className="text-sm text-gray-800 leading-relaxed" dangerouslySetInnerHTML={{ __html: highlighted }} />
      <div className="flex gap-3 mt-2 text-xs text-gray-400">
        {ts && <span>{ts}</span>}
        {meta.media_type && meta.media_type !== 'text' && (
          <span className="capitalize bg-gray-100 px-1.5 py-0.5 rounded">{meta.media_type}</span>
        )}
      </div>
    </div>
  )
}
