import { Search, Sparkles, Users, Send, Image, Bell, X, HelpCircle } from 'lucide-react'

const GUIDE = [
  {
    icon: Search,
    color: '#6366f1',
    label: 'Search & Find',
    examples: [
      "Find Priya's message about the project deadline",
      "What happened in Finance Team since Monday?",
      "Show messages from last 2 hours about the budget",
      "Search for all messages mentioning the client proposal",
    ],
  },
  {
    icon: Sparkles,
    color: '#7c3aed',
    label: 'Summarize',
    examples: [
      "Summarize this conversation",
      "Give me a summary of the Marketing group",
      "What did I miss in Project Launch while offline?",
      "Summarize the Finance Team chat from the last 3 days",
    ],
  },
  {
    icon: Users,
    color: '#0891b2',
    label: 'Team & Group',
    examples: [
      "Who is online in the Finance team right now?",
      "How active was the Design team this week?",
      "Show members of the Project Launch group",
      "How many messages did the team send this week?",
    ],
  },
  {
    icon: Send,
    color: '#059669',
    label: 'Messages & Actions',
    examples: [
      "Send the deadline reminder to Priya",
      "Draft a reply to Alex's message about the meeting",
      "Translate Raj's last message to English",
      "Set my status to busy",
    ],
  },
  {
    icon: Image,
    color: '#d97706',
    label: 'Documents & Media',
    examples: [
      "What files were shared in Project Launch?",
      "Show me unread images from today",
      "Find the Q2 report document",
      "List all documents shared in the Finance group",
    ],
  },
  {
    icon: Bell,
    color: '#dc2626',
    label: 'Personal & Reminders',
    examples: [
      "What tasks are assigned to me this week?",
      "Do I have any upcoming meetings?",
      "Remind me about the client call tomorrow at 3pm",
      "How many unread messages do I have?",
      "Show my saved reminders",
    ],
  },
]

export default function AIHelpGuide({ onSelect, onClose, compact = false }) {
  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div
        className={`flex items-center justify-between border-b border-indigo-100 flex-shrink-0 ${compact ? 'px-2.5 py-2' : 'px-4 py-3'}`}
        style={{ background: 'linear-gradient(to right, #eef2ff, #ede9fe)' }}
      >
        <div className="flex items-center gap-2">
          <HelpCircle size={compact ? 13 : 15} className="text-indigo-500" />
          <p className={`font-bold text-indigo-700 ${compact ? 'text-xs' : 'text-sm'}`}>
            What can I ask?
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-white/60 transition-all"
        >
          <X size={13} />
        </button>
      </div>

      {/* Subtitle */}
      <p className={`text-slate-400 text-xs flex-shrink-0 ${compact ? 'px-2.5 pt-2 pb-1' : 'px-4 pt-2.5 pb-1'}`}>
        Click any example to use it instantly ↓
      </p>

      {/* Category list */}
      <div className={`flex-1 overflow-y-auto space-y-3 ${compact ? 'px-2.5 pb-3' : 'px-4 pb-4'}`}>
        {GUIDE.map((cat) => (
          <div key={cat.label}>
            <div className="flex items-center gap-1.5 mb-1.5">
              <cat.icon size={compact ? 11 : 12} style={{ color: cat.color }} />
              <span className="text-xs font-semibold text-slate-600">{cat.label}</span>
            </div>
            <div className="space-y-0.5">
              {cat.examples.map((ex) => (
                <button
                  key={ex}
                  onClick={() => { onSelect(ex); onClose() }}
                  className={`w-full text-left text-slate-600 rounded-lg bg-white border border-slate-100 hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-700 transition-all ${
                    compact ? 'text-xs px-2.5 py-1.5' : 'text-xs px-3 py-2'
                  }`}
                >
                  "{ex}"
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
