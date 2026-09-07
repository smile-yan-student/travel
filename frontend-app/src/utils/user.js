/**
 * 用户会话工具：token / 用户名 本地持久化 + 登录态下的出行上报。
 * 未登录不记录任何出行（前端不调用、后端也忽略）。
 */
import { reportTrip, authMe, getTrips } from '../api'

const TOKEN_KEY = 'travel_token'
const USER_KEY = 'travel_username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}
export function getUserName() {
  return localStorage.getItem(USER_KEY) || ''
}
export function saveSession(token, username) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, username)
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
export function isLoggedIn() {
  return !!getToken()
}

/** 校验本地 token 是否仍有效（登录态恢复用） */
export async function refreshMe() {
  const token = getToken()
  if (!token) return null
  try {
    const res = await authMe()
    return res.user || null
  } catch (e) {
    clearSession()
    return null
  }
}

/** 登录用户上报一次出行；未登录静默跳过（不报错、不记录） */
export async function reportTripIfLoggedIn(payload) {
  if (!isLoggedIn()) return { recorded: false }
  try {
    const res = await reportTrip(payload)
    if (res && res.recorded) notifyTripsUpdated()
    return res
  } catch (e) {
    return { recorded: false }
  }
}

/** 通知首页刷新足迹（上报成功后广播） */
export function notifyTripsUpdated() {
  window.dispatchEvent(new CustomEvent('travel:trips-updated'))
}

/** 通知登录态变化（登录成功 / 退出登录），供对话等组件做会话同步 */
export function notifyUserChanged() {
  window.dispatchEvent(new CustomEvent('travel:user-changed'))
}

/** 拉取本人足迹汇总（未登录返回 null） */
export async function fetchMyTrips() {
  if (!isLoggedIn()) return null
  try {
    const res = await getTrips()
    return res.summary || null
  } catch (e) {
    return null
  }
}
