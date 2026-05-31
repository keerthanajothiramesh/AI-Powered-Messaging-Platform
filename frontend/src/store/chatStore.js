import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  activeConversation: null,
  conversations: [],
  groups: [],
  messages: {},
  onlineUsers: new Set(),
  lastSeen: {},
  typingUsers: {},
  unreadCounts: {},
  dmRefreshKey: 0,
  notifications: [],

  setActiveConversation: (conv) => set({ activeConversation: conv }),
  setConversations: (list) => set({ conversations: list }),
  setGroups: (list) => set({ groups: list }),

  updateGroup: (groupId, updates) =>
    set((s) => ({
      groups: s.groups.map((g) => g.group_id === groupId ? { ...g, ...updates } : g),
    })),

  removeGroup: (groupId) =>
    set((s) => ({
      groups: s.groups.filter((g) => g.group_id !== groupId),
      activeConversation: s.activeConversation?.id === groupId ? null : s.activeConversation,
    })),

  addMessage: (convId, message) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [convId]: [...(s.messages[convId] || []), message],
      },
    })),

  setMessages: (convId, msgs) =>
    set((s) => ({ messages: { ...s.messages, [convId]: msgs } })),

  updateMessageStatus: (convId, messageId, status) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [convId]: (s.messages[convId] || []).map((m) =>
          m.message_id === messageId ? { ...m, delivery_status: status } : m
        ),
      },
    })),

  updateMessage: (convId, messageId, content) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [convId]: (s.messages[convId] || []).map((m) =>
          m.message_id === messageId ? { ...m, content, edited: true } : m
        ),
      },
    })),

  removeMessage: (convId, messageId) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [convId]: (s.messages[convId] || []).map((m) =>
          m.message_id === messageId ? { ...m, content: '[Message deleted]', deleted: true } : m
        ),
      },
    })),

  bumpDmRefresh: () => set((s) => ({ dmRefreshKey: s.dmRefreshKey + 1 })),

  setLastSeen: (userId, ts) =>
    set((s) => ({ lastSeen: { ...s.lastSeen, [userId]: ts } })),

  setTyping: (convId) =>
    set((s) => ({ typingUsers: { ...s.typingUsers, [convId]: true } })),

  clearTyping: (convId) =>
    set((s) => {
      const next = { ...s.typingUsers }
      delete next[convId]
      return { typingUsers: next }
    }),

  incrementUnread: (convId) =>
    set((s) => ({
      unreadCounts: { ...s.unreadCounts, [convId]: (s.unreadCounts[convId] || 0) + 1 },
    })),

  clearUnread: (convId) =>
    set((s) => {
      const next = { ...s.unreadCounts }
      delete next[convId]
      return { unreadCounts: next }
    }),

  setReaction: (convId, messageId, reactions) =>
    set((s) => ({
      messages: {
        ...s.messages,
        [convId]: (s.messages[convId] || []).map((m) =>
          m.message_id === messageId ? { ...m, reactions } : m
        ),
      },
    })),

  setUserOnline: (userId) =>
    set((s) => ({ onlineUsers: new Set([...s.onlineUsers, userId]) })),

  setUserOffline: (userId, lastSeenAt) =>
    set((s) => {
      const next = new Set(s.onlineUsers)
      next.delete(userId)
      return {
        onlineUsers: next,
        lastSeen: { ...s.lastSeen, [userId]: lastSeenAt || new Date().toISOString() },
      }
    }),

  // Notifications
  setNotifications: (list) => set({ notifications: list }),

  addNotification: (notif) =>
    set((s) => {
      const exists = s.notifications.some((n) => n.notification_id === notif.notification_id)
      if (exists) return s
      return { notifications: [notif, ...s.notifications].slice(0, 100) }
    }),

  markNotificationsRead: () =>
    set((s) => ({
      notifications: s.notifications.map((n) => ({ ...n, is_read: true })),
    })),
}))
