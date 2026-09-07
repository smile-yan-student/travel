/**
 * 对话历史持久化与同步：
 * - 未登录：会话存 localStorage（页面切换 / 刷新后保留）。
 * - 登录后：自动把本地会话同步到后端（按用户存储），随后走后端读写。
 * - 登录用户可管理多条历史会话（列表 / 加载 / 新建 / 删除）。
 */
import {
  listConversations, getConversation, saveConversation, deleteConversation, conversationStream,
} from '../api'
import { isLoggedIn } from './user'

const LOCAL_KEY = 'travel_convo_local'

// ---------- 未登录本地存储 ----------

export function loadLocalConvo() {
  try {
    const raw = localStorage.getItem(LOCAL_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}
export function saveLocalConvo(data) {
  localStorage.setItem(LOCAL_KEY, JSON.stringify(data))
}
export function clearLocalConvo() {
  localStorage.removeItem(LOCAL_KEY)
}

// ---------- 后端（登录用户，自动带 token） ----------

export async function fetchConvoList(params = {}) {
  const res = await listConversations(params)
  return res.conversations || []
}
export async function fetchConvoStream(params = {}) {
  const res = await conversationStream(params)
  return res.conversations || []
}
export async function fetchConvo(id) {
  const res = await getConversation(id)
  return res.conversation
}
export async function persistConvo(payload) {
  const res = await saveConversation(payload)
  return res.conversation
}
export async function removeConvo(id) {
  return deleteConversation(id)
}

/** 会话标题：取第一条用户消息，截断 */
export function deriveTitle(messages) {
  const firstUser = (messages || []).find((m) => m.role === 'user')
  if (!firstUser || !firstUser.content) return '未命名对话'
  const t = firstUser.content.replace(/\s+/g, ' ').trim()
  return t.length > 20 ? t.slice(0, 20) + '…' : t
}

/**
 * 恢复 / 同步会话（进入对话板块、登录态变化时调用）：
 * - 未登录：返回本地会话（可能为 null → 空对话）。
 * - 登录：若本地有待同步会话 → 先同步到后端并清除本地；再返回最近一条后端会话。
 * 返回 { source: 'local'|'remote'|'empty', messages, conversationId, title }
 */
export async function restoreOrSync() {
  if (!isLoggedIn()) {
    const local = loadLocalConvo()
    if (local && local.messages && local.messages.length) {
      return {
        source: 'local',
        messages: local.messages,
        title: local.title,
        conversationId: null,
      }
    }
    return { source: 'empty', messages: [], title: '', conversationId: null }
  }

  // 登录：先同步未登录本地会话 → 后端
  const local = loadLocalConvo()
  if (local && local.messages && local.messages.length) {
    try {
      const conv = await persistConvo({
        title: local.title || deriveTitle(local.messages),
        messages: local.messages,
      })
      clearLocalConvo()
      return { source: 'remote', messages: conv.messages, title: conv.title, conversationId: conv.id }
    } catch (e) {
      /* 同步失败则回落本地 */
      return { source: 'local', messages: local.messages, title: local.title, conversationId: null }
    }
  }

  // 无本地待同步 → 加载最近一条后端会话
  try {
    const list = await fetchConvoList()
    if (list.length) {
      const conv = await fetchConvo(list[0].id)
      return { source: 'remote', messages: conv.messages, title: conv.title, conversationId: conv.id }
    }
  } catch (e) {
    /* 后端不可用则空 */
  }
  return { source: 'empty', messages: [], title: '', conversationId: null }
}
