import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { X, Loader2, UserPlus, Check } from 'lucide-react'
import client from '../api/client'
import { useChatStore } from '../store/chatStore'
import toast from 'react-hot-toast'

export default function GroupModal({ onClose }) {
  const { t } = useTranslation()
  const { setGroups } = useChatStore()
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [loading, setLoading] = useState(false)
  const [searchQ, setSearchQ] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [selectedMembers, setSelectedMembers] = useState([])
  const [searching, setSearching] = useState(false)

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

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Add Members <span className="text-gray-400 font-normal">(search by name)</span>
            </label>
            <div className="relative">
              <UserPlus size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchQ}
                onChange={(e) => handleSearch(e.target.value)}
                className="w-full pl-9 pr-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20"
                placeholder="Search people..."
              />
            </div>

            {/* Search results dropdown */}
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

            {/* Selected members chips */}
            {selectedMembers.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
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
          </div>

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
