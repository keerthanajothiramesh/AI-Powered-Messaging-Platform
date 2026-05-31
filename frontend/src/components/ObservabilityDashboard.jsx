import { useState, useEffect, useCallback } from 'react'
import { RefreshCw, Activity, MessageSquare, Brain, Users, TrendingUp, AlertTriangle, CheckCircle } from 'lucide-react'
import client from '../api/client'

const REFRESH_INTERVAL_MS = 30_000

function StatCard({ icon: Icon, label, value, sub, color = 'indigo', alert = false }) {
  const colors = {
    indigo: 'bg-indigo-50 text-indigo-600',
    green:  'bg-emerald-50 text-emerald-600',
    amber:  'bg-amber-50 text-amber-600',
    red:    'bg-red-50 text-red-600',
    purple: 'bg-purple-50 text-purple-600',
  }
  return (
    <div className={`bg-white rounded-2xl p-5 shadow-sm border ${alert ? 'border-red-200' : 'border-slate-100'}`}>
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${colors[color]}`}>
          <Icon className="w-5 h-5" />
        </div>
        {alert && <AlertTriangle className="w-4 h-4 text-red-400" />}
      </div>
      <div className="text-2xl font-bold text-slate-900 leading-tight">{value}</div>
      <div className="text-sm font-medium text-slate-500 mt-0.5">{label}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  )
}

function QualityBar({ label, score, max = 10 }) {
  const pct = Math.min((score / max) * 100, 100)
  const color = pct >= 70 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-400' : 'bg-red-400'
  return (
    <div className="mb-3">
      <div className="flex justify-between text-xs text-slate-600 mb-1">
        <span>{label}</span>
        <span className="font-semibold">{typeof score === 'number' ? score.toFixed(1) : score} / {max}</span>
      </div>
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function ObservabilityDashboard({ onClose }) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [lastRefresh, setLastRefresh] = useState(null)

  const fetchMetrics = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const r = await client.get('/metrics/summary')
      setData(r.data)
      setLastRefresh(new Date())
    } catch (e) {
      setError('Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMetrics()
    const id = setInterval(fetchMetrics, REFRESH_INTERVAL_MS)
    return () => clearInterval(id)
  }, [fetchMetrics])

  const msgs     = data?.messages     || {}
  const aiQ      = data?.ai_quality   || {}
  const users    = data?.users        || {}
  const deliveryOk = (msgs.delivery_rate_pct ?? 100) >= 95

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-slate-50 rounded-3xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-slate-200 bg-white rounded-t-3xl">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="font-bold text-slate-900 text-base">Observability Dashboard</h2>
              <p className="text-xs text-slate-400">
                {lastRefresh ? `Updated ${lastRefresh.toLocaleTimeString()}` : 'Loading…'} · auto-refreshes every 30 s
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchMetrics}
              disabled={loading}
              className="p-2 rounded-xl hover:bg-slate-100 text-slate-500 transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button onClick={onClose} className="p-2 rounded-xl hover:bg-slate-100 text-slate-400 transition-colors text-lg leading-none">×</button>
          </div>
        </div>

        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 rounded-xl text-sm text-red-600">{error}</div>
        )}

        {loading && !data ? (
          <div className="flex items-center justify-center py-20 text-slate-400 text-sm">Loading metrics…</div>
        ) : (
          <div className="p-6 space-y-6">

            {/* Message delivery KPIs */}
            <section>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Message Delivery</h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <StatCard
                  icon={MessageSquare}
                  label="Total Messages"
                  value={(msgs.total ?? 0).toLocaleString()}
                  color="indigo"
                />
                <StatCard
                  icon={CheckCircle}
                  label="Delivered"
                  value={(msgs.delivered ?? 0).toLocaleString()}
                  color="green"
                />
                <StatCard
                  icon={AlertTriangle}
                  label="Failed / Queued"
                  value={(msgs.failed_or_queued ?? 0).toLocaleString()}
                  color={msgs.failed_or_queued > 0 ? 'red' : 'green'}
                  alert={msgs.failed_or_queued > 0}
                />
                <StatCard
                  icon={TrendingUp}
                  label="Delivery Rate"
                  value={`${msgs.delivery_rate_pct ?? 0}%`}
                  sub={deliveryOk ? '≥ 95% SLA ✓' : '< 95% SLA ✗'}
                  color={deliveryOk ? 'green' : 'red'}
                  alert={!deliveryOk}
                />
              </div>
            </section>

            {/* AI quality */}
            <section>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">AI Quality (LLM-as-Judge)</h3>
              <div className="bg-white rounded-2xl border border-slate-100 p-5 shadow-sm">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
                  <div className="text-center">
                    <div className="text-2xl font-bold text-indigo-600">{aiQ.total_evaluations ?? 0}</div>
                    <div className="text-xs text-slate-500 mt-0.5">Evaluations</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-slate-900">{aiQ.avg_judge_score ?? '—'}</div>
                    <div className="text-xs text-slate-500 mt-0.5">Avg Score / 10</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-emerald-600">👍 {aiQ.thumbs_up ?? 0}</div>
                    <div className="text-xs text-slate-500 mt-0.5">User Thumbs Up</div>
                  </div>
                  <div className="text-center">
                    <div className="text-2xl font-bold text-red-500">👎 {aiQ.thumbs_down ?? 0}</div>
                    <div className="text-xs text-slate-500 mt-0.5">User Thumbs Down</div>
                  </div>
                </div>
                <QualityBar label="High-quality responses (score ≥ 7)" score={aiQ.high_quality_pct ?? 0} max={100} />
                <QualityBar label="Average judge score" score={(aiQ.avg_judge_score ?? 0) * 10} max={100} />
              </div>
            </section>

            {/* Users */}
            <section>
              <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3">Active Users</h3>
              <div className="grid grid-cols-2 gap-3">
                <StatCard
                  icon={Users}
                  label="Online Now"
                  value={users.online ?? 0}
                  color="purple"
                />
                <StatCard
                  icon={Brain}
                  label="AI Evaluations"
                  value={(aiQ.total_evaluations ?? 0).toLocaleString()}
                  sub="summaries + chatbot responses"
                  color="indigo"
                />
              </div>
            </section>

            {/* Prometheus link */}
            <div className="bg-white rounded-2xl border border-slate-100 p-4 shadow-sm">
              <p className="text-xs text-slate-500">
                Raw Prometheus metrics available at{' '}
                <code className="bg-slate-100 px-1 rounded text-indigo-600">/metrics</code>
                {' '}— scrape with Prometheus + visualise in Grafana for time-series dashboards.
              </p>
            </div>

          </div>
        )}
      </div>
    </div>
  )
}
