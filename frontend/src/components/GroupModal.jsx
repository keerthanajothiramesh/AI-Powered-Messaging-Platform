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
  const [tab, setTab] = useState('search') // 'search' | 'import'

  // Search state
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [selectedMembers, setSelectedMembers] = useState([])
  const [searching, setSearching] = useState(false)

  // Import state
  const fileRef = useRef(null)
  const [importRows, setImportRows] = useState([]) // [{ name, email, user_id, display_name, found, added }]
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

      // Normalise column names — accept Name/name/NAME and Email/email/EMAIL
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
      if (parsed.length > 99) {
        toast(`Only first 99 members will be imported (group cap is 100).`, { icon: 'ℹ️' })
      }

      setResolving(true)
      const emails = capped.map((r) => r.email)
      const res = await client.post('/users/resolve-by-email', { emails })
      const resolvedMap = {}
      res.data.forEach((r) => { resolvedMap[r.email] = r })

      setImportRows(
        capped.map((r) => ({
          ...r,
          ...resolvedMap[r.email],
          added: false,
        }))
      )
    } catch (err) {
      toast.error('Failed to parse file')
    } finally {
      setResolving(false)
    }
  }

  const addAllFound = () => {
    const found = importRows.filter((r) => r.found && !isSelected({ user_id: r.user_id }))
    setSelectedMembers((prev) => [
      ...prev,
      ...found.map((r) => ({ user_id: r.user_id, display_name: r.display_name })),
    ])
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
      const newGroup = {
        group_id: res.data.group_id,
        group_name: name,
        description: desc,
        member_count: selectedMembers.length + 1,
      }
      const current = useChatStore.getState().groups
      if (!current.find((g) => g.group_id === newGroup.group_id)) {
        setGroups([...current, newGroup])
      }
      toast.success('Group created!')
      onClose()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create group')
    } finally { setLoading(false) }
  }

  const foundCount = importRows.filter((r) => r.found).length
  const notFoundCount = importRows.filter((r) => !r.found).length

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="w-full max-w-md bg-white rounded-2xl shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">{t('groups.create')}</h2>
          <button onClick={onClose}><X size={18} /></button>
        </div>

        <form onSubmit={handleCreate} className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Group Name *</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20"
              placeholder="e.g. Project Launch Team"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
            <textarea
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              rows={2}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 resize-none"
            />
          </div>

          {/* Tab switcher */}
          <div>
            <div className="flex gap-1 mb-3 bg-gray-100 rounded-lg p-1">
              <button
                type="button"
                onClick={() => setTab('search')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-sm rounded-md font-medium transition-colors ${
                  tab === 'search' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <UserPlus size={14} /> Search
              </button>
              <button
                type="button"
                onClick={() => setTab('import')}
                className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 text-sm rounded-md font-medium transition-colors ${
                  tab === 'import' ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                <FileSpreadsheet size={14} /> Import Excel
              </button>
            </div>

            {tab === 'search' && (
              <div>
                <div className="relative">
                  <UserPlus size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                  <input
                    value={searchQ}
                    onChange={(e) => handleSearch(e.target.value)}
                    className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Search people..."
                  />
                </div>
                {searchResults.length > 0 && (
                  <div className="mt-1 border border-gray-100 rounded-lg overflow-hidden shadow-sm max-h-36 overflow-y-auto">
                    {searchResults.map((u) => (
                      <button
                        key={u.user_id}
                        type="button"
                        onClick={() => toggleMember(u)}
                        className="w-full flex items-center gap-3 px-3 py-2 hover:bg-gray-50 text-left"
                      >
                        <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center text-white text-xs font-semibold flex-shrink-0">
                          {u.display_name.slice(0, 2).toUpperCase()}
                        </div>
                        <span className="flex-1 text-sm text-gray-800">{u.display_name}</span>
                        {isSelected(u) && <Check size={15} className="text-primary flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                )}
                {searching && <p className="text-xs text-gray-400 mt-1">Searching...</p>}
              </div>
            )}

            {tab === 'import' && (
              <div className="space-y-3">
                <div
                  className="border-2 border-dashed border-gray-200 rounded-xl p-5 flex flex-col items-center gap-2 cursor-pointer hover:border-primary/40 hover:bg-primary/5 transition-colors"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload size={22} className="text-gray-400" />
                  <p className="text-sm text-gray-600 font-medium">Upload Excel or CSV file</p>
                  <p className="text-xs text-gray-400">File must have <strong>Name</strong> and <strong>Email</strong> columns</p>
                  <input
                    ref={fileRef}
                    type="file"
                    accept=".xlsx,.xls,.csv"
                    className="hidden"
                    onChange={handleFileChange}
                  />
                </div>

                {resolving && (
                  <p className="text-xs text-gray-400 flex items-center gap-1.5">
                    <Loader2 size={12} className="animate-spin" /> Resolving emails…
                  </p>
                )}

                {importRows.length > 0 && (
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs text-gray-500">
                        <span className="text-green-600 font-medium">{foundCount} found</span>
                        {notFoundCount > 0 && (
                          <span className="ml-2 text-red-400">{notFoundCount} not registered</span>
                        )}
                      </span>
                      {foundCount > 0 && (
                        <button
                          type="button"
                          onClick={addAllFound}
                          className="text-xs text-primary font-medium hover:underline"
                        >
                          Add all found
                        </button>
                      )}
                    </div>
                    <div className="border border-gray-100 rounded-lg overflow-hidden max-h-44 overflow-y-auto">
                      <table className="w-full text-xs">
                        <thead className="bg-gray-50 text-gray-500 uppercase tracking-wide">
                          <tr>
                            <th className="px-3 py-2 text-left">Name</th>
                            <th className="px-3 py-2 text-left">Email</th>
                            <th className="px-3 py-2 text-center">Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {importRows.map((row, i) => (
                            <tr key={i} className="border-t border-gray-50">
                              <td className="px-3 py-2 text-gray-800">{row.display_name || row.name || '—'}</td>
                              <td className="px-3 py-2 text-gray-500 truncate max-w-[120px]">{row.email}</td>
                              <td className="px-3 py-2 text-center">
                                {row.found ? (
                                  row.added || isSelected({ user_id: row.user_id }) ? (
                                    <span className="inline-flex items-center gap-0.5 text-green-600 font-medium"><Check size={11} /> Added</span>
                                  ) : (
                                    <button
                                      type="button"
                                      onClick={() => {
                                        toggleMember({ user_id: row.user_id, display_name: row.display_name })
                                        setImportRows((prev) => prev.map((r, idx) => idx === i ? { ...r, added: true } : r))
                                      }}
                                      className="text-primary hover:underline font-medium"
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

          {/* Selected member chips — always visible regardless of tab */}
          {selectedMembers.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {selectedMembers.map((m) => (
                <span
                  key={m.user_id}
                  className="flex items-center gap-1 bg-red-50 text-primary text-xs px-2 py-1 rounded-full"
                >
                  {m.display_name}
                  <button type="button" onClick={() => toggleMember(m)}>
                    <X size={11} />
                  </button>
                </span>
              ))}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !name.trim()}
            className="w-full py-2.5 bg-primary text-white rounded-lg font-medium hover:bg-primary-dark disabled:opacity-60 transition-colors"
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
