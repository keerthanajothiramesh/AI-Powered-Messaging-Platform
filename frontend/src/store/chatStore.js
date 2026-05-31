import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  activeConversation: null,
  conversations: [],
  groups: [],
  messages: {},
  onlineUsers: new Set(),

  setActiveConversation: (conv) => set({ activeConversation: conv }),
  setConversations: (list) => set({ conversations: list }),
  setGroups: (list) => set({ groups: list }),

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

  setUserOnline: (userId) =>
    set((s) => ({ onlineUsers: new Set([...s.onlineUsers, userId]) })),

  setUserOffline: (userId) =>
    set((s) => {
      const next = new Set(s.onlineUsers)
      next.delete(userId)
      return { onlineUsers: next }
    }),
}))
