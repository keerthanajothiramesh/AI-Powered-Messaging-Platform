import { useEffect, useRef, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'
import { useChatStore } from '../store/chatStore'
import toast from 'react-hot-toast'

const WS_BASE = import.meta.env.VITE_WS_URL || 'ws://localhost:8000'

export function useWebSocket() {
  const ws = useRef(null)
  const reconnectTimeout = useRef(null)
  const { token, user } = useAuthStore()
  const { addMessage, updateMessageStatus, setUserOnline, setUserOffline, activeConversation } = useChatStore()

  const connect = useCallback(() => {
    if (!token || !user) return
    if (ws.current?.readyState === WebSocket.OPEN) return

    const url = `${WS_BASE}/ws/${user.user_id}?token=${token}`
    ws.current = new WebSocket(url)

    ws.current.onopen = () => {
      console.info('[WS] Connected')
      if (reconnectTimeout.current) {
        clearTimeout(reconnectTimeout.current)
        reconnectTimeout.current = null
      }
    }

    ws.current.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data)
        handleEvent(payload)
      } catch (e) {
        console.warn('[WS] Parse error', e)
      }
    }

    ws.current.onclose = () => {
      console.warn('[WS] Disconnected, reconnecting in 3s...')
      reconnectTimeout.current = setTimeout(connect, 3000)
    }

    ws.current.onerror = (e) => {
      console.error('[WS] Error', e)
    }
  }, [token, user])

  const handleEvent = useCallback((payload) => {
    const { type, data } = payload
    if (type === 'connected') {
      if (data.queued_count > 0) {
        toast(`📬 ${data.queued_count} message${data.queued_count > 1 ? 's' : ''} delivered from while you were offline`)
      }
    } else if (type === 'message') {
      const currentUserId = useAuthStore.getState().user?.user_id
      const convId = data.group_id
        || (data.sender_id === currentUserId ? data.receiver_id : data.sender_id)
      addMessage(convId, data)
      if (convId !== useChatStore.getState().activeConversation?.id) {
        toast(`New message from ${data.sender_id?.slice(0, 8)}…`, { icon: '💬' })
      }
    } else if (type === 'group_added') {
      const { groups } = useChatStore.getState()
      if (!groups.find((g) => g.group_id === data.group_id)) {
        useChatStore.getState().setGroups([
          ...groups,
          { group_id: data.group_id, group_name: data.group_name, description: data.description, member_count: data.member_count },
        ])
        toast(`You were added to "${data.group_name}"`, { icon: '👥' })
      }
    } else if (type === 'message_edited') {
      const currentUserId = useAuthStore.getState().user?.user_id
      const convId = data.group_id
        || (data.sender_id === currentUserId ? data.receiver_id : data.sender_id)
      if (convId) useChatStore.getState().updateMessage(convId, data.message_id, data.content)
    } else if (type === 'message_deleted') {
      const currentUserId = useAuthStore.getState().user?.user_id
      const convId = data.group_id
        || (data.sender_id === currentUserId ? data.receiver_id : data.sender_id)
      if (convId) useChatStore.getState().removeMessage(convId, data.message_id)
    } else if (type === 'message_read') {
      const active = useChatStore.getState().activeConversation
      if (active) updateMessageStatus(active.id, data.message_id, 'read')
    } else if (type === 'user_online') {
      useChatStore.getState().setUserOnline(data.user_id)
    } else if (type === 'user_offline') {
      useChatStore.getState().setUserOffline(data.user_id, data.last_seen)
    } else if (type === 'notification') {
      toast(data.body, { icon: '🔔' })
    }
  }, [addMessage, updateMessageStatus])

  const send = useCallback((event) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(event))
    }
  }, [])

  const sendMessage = useCallback((content, convId, isGroup = false, mediaType = 'text', mediaUrl = null) => {
    send({
      type: 'send_message',
      data: {
        content,
        ...(isGroup ? { group_id: convId } : { receiver_id: convId }),
        media_type: mediaType,
        media_url: mediaUrl,
      },
    })
  }, [send])

  const sendTyping = useCallback((convId, isGroup = false) => {
    send({
      type: 'typing',
      data: isGroup ? { group_id: convId } : { receiver_id: convId },
    })
  }, [send])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current)
      ws.current?.close()
    }
  }, [connect])

  return { sendMessage, sendTyping, send }
}
