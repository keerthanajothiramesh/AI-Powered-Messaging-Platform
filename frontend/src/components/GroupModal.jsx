import { useState, useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Loader2, UserPlus, Check, FileSpreadsheet, Upload, AlertCircle } from 'lucide-react'
import * as XLSX from 'xlsx'
import client from '../api/client'
import { useChatStore } from '../store/chatStore'
import toast from 'react-hot-toast'

export default function GroupModal({ onClose }) {
  const { t } = useTranslation()
  const { setGroups } = useChatStore()
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [tab, setTab] = useState('search')

  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [selectedMembers, setSelectedMembers] = useState([])
  const [searching, setSearching] = useState(false)

  const fileRef = useRef(null)
  const [importRows, setImportRows] = useState([])
  const [resolving, setResolving] = useState(false)

  const handleSearch = useCallback(async (q) => {
    setSearchQ(q)
    if (q.length < 2) { setSearchResults([]); return }
    setSearching(true)
    try {
      const r = await client.get(`/users/search?q=${encodeURIComponent(q)}`)
      setSearchResults(r.data)
    } catch { setSearchResults([]) }
    finally { setSearching(false) }
  }, [])

  const toggleMember = (u) => {
    setSelectedMembers((prev) =>
      prev.find((m) => m.user_id === u.user_id)
        ? prev.filter((m) => m.user_id !== u.user_id)
        : [...prev, u]
    )
  }

  const isSelected = (u) => selectedMembers.some((m) => m.user_id === u.user_id)

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    e.target.value = ''
    try {
      const buffer = await file.arrayBuffer()
      const wb = XLSX.read(buffer, { type: 'array' })
      const ws = wb.Sheets[wb.SheetNames[0]]
      const rows = XLSX.utils.sheet_to_json(ws, { defval: '' })
      const parsed = rows
        .map((row) => {
          const keys = Object.keys(row)
          const nameKey = keys.find((k) => k.trim().toLowerCase() === 'name')
          const emailKey = keys.find((k) => k.trim().toLowerCase() === 'email')
          return {
            name: nameKey ? String(row[nameKey]).trim() : '',
            email: emailKey ? String(row[emailKey]).trim().toLowerCase() : '',
          }
        })
        .filter((r) => r.email)

      if (parsed.length === 0) {
        toast.error('No valid rows found. Make sure your file has "Name" and "Email" columns.')
        return
      }

      const capped = parsed.slice(0, 99)
      if (parsed.length > 99) toast(`Only first 99 members will be imported.`, { icon: 'ℹ️' })

      setResolving(true)
      const emails = capped.map((r) => r.email)
      const res = await client.post('/users/resolve-by-email', { emails })
      const resolvedMap = {}
      res.data.forEach((r) => { resolvedMap[r.email] = r })
      setImportRows(capped.map((r) => ({ ...r, ...resolvedMap[r.email], added: false })))
    } catch {
      toast.error('Failed to parse file')
    } finally {
      setResolving(false)
    }
  }

  const addAllFound = () => {
    const found = importRows.filter((r) => r.found && !isSelected({ user_id: r.user_id }))
    setSelectedMembers((prev) => [...prev, ...found.map((r) => ({ user_id: r.user_id, display_name: r.display_name }))])
    setImportRows((prev) => prev.map((r) => (r.found ? { ...r, added: true } : r)))
    toast.success(`${found.length} member${found.length !== 1 ? 's' : ''} added`)
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    if (!name.trim()) return
    setLoading(true)
    try {
      const res = await client.post('/groups', {
        group_name: name,
        description: desc,
        member_ids: selectedMembers.map((m) => m.user_id),
      })
      const newGroup = { group_id: res.data.group_id, group_name: name, description: desc, member_count: selectedMembers.length + 1 }
      const current = useChatStore.getState().groups
      if (!current.find((g) => g.group_id === newGroup.group_id)) setGroups([...current, newGroup])
      toast.success('Group created!')
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create group')
    } finally { setLoading(false) }
  }

  const foundCount = importRows.filter((r) => r.found).length
  const notFoundCount = importRows.filter((r) => !r.found).length

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(30, 27, 75, 0.55)', backdropFilter: 'blur(4px)' }}
      onClick={onClose}
    >
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl overflow-hidden border border-indigo-100" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4"
             style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}>
          <h2 className="font-bold text-white">{t('groups.create')}</h2>
          <button onClick={onClose} className="p-1 text-white/60 hover:text-white rounded-lg hover:bg-white/15 transition-all">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleCreate} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Group Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-all"
              placeholder="e.g. Project Launch Team"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Description</label>
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={2}
              className="w-full px-3 py-2.5 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 resize-none transition-all"
            />
          </div>

          {/* Tab switcher */}
          <div>
            <div className="flex gap-1 mb-3 bg-slate-100 rounded-xl p-1">
              <button
                type="button"
                onClick={() => setTab('search')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-sm rounded-lg font-semibold transition-all ${
                  tab === 'search' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <UserPlus size={14} /> Search
              </button>
              <button
                type="button"
                onClick={() => setTab('import')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 text-sm rounded-lg font-semibold transition-all ${
                  tab === 'import' ? 'bg-white shadow-sm text-indigo-600' : 'text-slate-500 hover:text-slate-700'
                }`}
              >
                <FileSpreadsheet size={14} /> Import Excel
              </button>
            </div>

            {tab === 'search' && (
              <div>
                <div className="relative">
                  <UserPlus size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    value={searchQ}
                    onChange={(e) => handleSearch(e.target.value)}
                    className="w-full pl-9 pr-3 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 focus:border-indigo-400 transition-all"
                    placeholder="Search people..."
                  />
                </div>
                {searchResults.length > 0 && (
                  <div className="mt-1 border border-slate-100 rounded-xl overflow-hidden shadow-sm max-h-36 overflow-y-auto">
                    {searchResults.map((u) => (
                      <button
                        key={u.user_id}
                        type="button"
                        onClick={() => toggleMember(u)}
                        className="w-full flex items-center gap-3 px-3 py-2.5 hover:bg-indigo-50 text-left transition-all"
                      >
                        <div
                          className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold flex-shrink-0"
                          style={{ background: 'linear-gradient(135deg, #818cf8, #7c3aed)' }}
                        >
                          {u.display_name.slice(0, 2).toUpperCase()}
                        </div>
                        <span className="flex-1 text-sm text-slate-800 font-medium">{u.display_name}</span>
                        {isSelected(u) && <Check size={15} className="text-indigo-600 flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                )}
                {searching && <p className="text-xs text-slate-400 mt-1">Searching...</p>}
              </div>
            )}

            {tab === 'import' && (
              <div className="space-y-3">
                <div
                  className="border-2 border-dashed border-indigo-200 rounded-2xl p-5 flex flex-col items-center gap-2 cursor-pointer hover:border-indigo-400 hover:bg-indigo-50/30 transition-all"
                  onClick={() => fileRef.current?.click()}
                >
                  <div className="w-10 h-10 rounded-xl flex items-center justify-center"
                       style={{ background: 'linear-gradient(135deg, #eef2ff, #ede9fe)' }}>
                    <Upload size={18} className="text-indigo-500" />
                  </div>
                  <p className="text-sm text-slate-600 font-semibold">Upload Excel or CSV file</p>
                  <p className="text-xs text-slate-400">File must have <strong>Name</strong> and <strong>Email</strong> columns</p>
                  <input ref={fileRef} type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={handleFileChange} />
                </div>

                {resolving && (
                  <p className="text-xs text-slate-400 flex items-center gap-1.5">
                    <Loader2 size={12} className="animate-spin text-indigo-400" /> Resolving emails…
                  </p>
                )}

                {importRows.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-slate-500">
                        <span className="text-emerald-600 font-semibold">{foundCount} found</span>
                        {notFoundCount > 0 && <span className="ml-2 text-red-400">{notFoundCount} not registered</span>}
                      </span>
                      {foundCount > 0 && (
                        <button type="button" onClick={addAllFound} className="text-xs text-indigo-600 font-semibold hover:underline">
                          Add all found
                        </button>
                      )}
                    </div>
                    <div className="border border-slate-100 rounded-xl overflow-hidden max-h-44 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead className="text-slate-500 uppercase tracking-wide" style={{ background: 'linear-gradient(135deg, #f0f4ff, #f5f3ff)' }}>
                          <tr>
                            <th className="px-3 py-2 text-left">Name</th>
                            <th className="px-3 py-2 text-left">Email</th>
                            <th className="px-3 py-2 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {importRows.map((row, i) => (
                            <tr key={i} className="border-t border-slate-50">
                              <td className="px-3 py-2 text-slate-800">{row.display_name || row.name || '—'}</td>
                              <td className="px-3 py-2 text-slate-500 truncate max-w-[120px]">{row.email}</td>
                              <td className="px-3 py-2 text-center">
                                {row.found ? (
                                  row.added || isSelected({ user_id: row.user_id }) ? (
                                    <span className="inline-flex items-center gap-0.5 text-emerald-600 font-semibold"><Check size={11} /> Added</span>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        toggleMember({ user_id: row.user_id, display_name: row.display_name })
                                        setImportRows((prev) => prev.map((r, idx) => idx === i ? { ...r, added: true } : r))
                                      }}
                                      className="text-indigo-600 hover:underline font-semibold"
                                    >
                                      Add
                                    </button>
                                  )
                                ) : (
                                  <span className="inline-flex items-center gap-0.5 text-red-400"><AlertCircle size={11} /> Not found</span>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {selectedMembers.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedMembers.map((m) => (
                <span key={m.user_id} className="flex items-center gap-1 bg-indigo-50 text-indigo-700 text-xs px-2.5 py-1 rounded-full border border-indigo-100 font-medium">
                  {m.display_name}
                  <button type="button" onClick={() => toggleMember(m)} className="hover:text-indigo-900 transition-colors">
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !name.trim()}
            className="w-full py-3 text-white rounded-xl font-bold disabled:opacity-60 transition-all shadow-md"
            style={{ background: 'linear-gradient(135deg, #6366f1, #7c3aed)' }}
          >
            {loading
              ? <><Loader2 size={16} className="inline animate-spin mr-2" />Creating...</>
              : `Create Group${selectedMembers.length > 0 ? ` with ${selectedMembers.length + 1} members` : ''}`
            }
          </button>
        </form>
      </div>
    </div>
  )
}
