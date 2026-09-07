<template>
  <div class="chat-planner">
    <!-- 顶部工具行：仅保留"新对话"（历史会话已并入统一消息流） -->
    <div class="convo-bar">
      <span class="convo-hint">历史对话都在下方，向上滑动可查看更多</span>
      <button class="convo-btn ghost" @click="newConversation">🆕 新对话</button>
    </div>

    <!-- 统一消息流：当前会话 + 历史会话按时间连续展示，滚到顶部加载更早 -->
    <div ref="listEl" class="msg-list" @scroll.passive="onListScroll">
      <div v-if="olderLoading" class="stream-tip">加载更早的对话…</div>
      <div v-else-if="olderEnded && olderLoadedAny" class="stream-tip">· 这是最早的对话 ·</div>
      <template v-for="(item, i) in flat" :key="i">
        <div v-if="item.kind === 'divider'" class="stream-divider">
          <span class="divider-title">{{ item.title }}</span>
          <span class="divider-date">{{ item.date }}</span>
        </div>
        <div v-else :class="['msg', item.role]">
          <div v-if="item.role === 'user'" class="avatar user-avatar">我</div>
          <div v-else class="avatar ai-avatar">AI</div>
          <div class="bubble">
            <span v-if="item.loading" class="typing"><i /><i /><i /></span>
            <template v-else>
              <span class="text">{{ item.content }}</span>
              <button v-if="item.plan" class="view-btn" @click="openPlan(item.plan)">
                🗺 查看生成行程（{{ item.plan.days }}天 · {{ item.plan.all_pois.length }}点位）→
              </button>
            </template>
          </div>
        </div>
      </template>

      <!-- 空状态快捷示例 -->
      <div v-if="flat.length === 0" class="samples">
        <p class="samples-tip">不知道怎么开口？试试这样说：</p>
        <button v-for="s in SAMPLES" :key="s" class="sample" @click="send(s)">{{ s }}</button>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-bar">
      <input
        v-model="draft"
        class="chat-input"
        placeholder="说说你想去哪儿，例如：带爸妈去杭州玩3天…"
        :disabled="sending"
        @keyup.enter="send()"
      />
      <button class="send-btn" :disabled="sending || !draft.trim()" @click="send()">
        <span v-if="sending" class="spinner" />
        <span v-else>发送</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { chatPlan, learnFromPlan } from '../api'
import { reportTripIfLoggedIn, isLoggedIn, getToken } from '../utils/user'
import { setCurrentPlan } from '../store'
import {
  saveLocalConvo, restoreOrSync, persistConvo, fetchConvoStream, deriveTitle,
} from '../utils/convo'

const router = useRouter()
const SAMPLES = [
  '带爸妈去杭州玩3天，预算适中，想逛西湖吃小吃',
  '和对象去上海2天，经济一点，喜欢夜景和购物',
  '一个人去成都4天，节奏慢一点，喜欢美食',
  '带娃去北京3天，轻松点，想看故宫',
]

const flat = ref([]) // 统一消息流：[{kind:'divider',...} | {kind:'msg',role,content,plan,loading}]
const draft = ref('')
const sending = ref(false)
const listEl = ref(null)

// 当前会话状态
const loggedIn = ref(false)
const currentConvId = ref(null)
const currentTitle = ref('')
const olderLoading = ref(false)
const olderEnded = ref(false)
const olderLoadedAny = ref(false)
let oldestConvId = null // 最早已加载会话 id（向上加载更早的游标）
let restoring = false

let persistChain = Promise.resolve()
let persistTimer = null

function welcomeText() {
  return '你好呀，我是你的旅行伙伴「去见山海」🌍 世界很大，而我们正从一次出发开始。你想去哪儿？哪怕只是心里一个模糊的方向，也可以说给我听。'
}
function todayStr() {
  const d = new Date()
  return `${d.getMonth() + 1}月${d.getDate()}日`
}
function shortDate(ts) {
  if (!ts) return ''
  const d = ts.slice(0, 10)
  const today = new Date()
  const t = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`
  if (d === t) return '今天'
  const y = new Date(Date.now() - 86400000)
  const ystr = `${y.getFullYear()}-${String(y.getMonth() + 1).padStart(2, '0')}-${String(y.getDate()).padStart(2, '0')}`
  if (d === ystr) return '昨天'
  return ts.slice(5, 10).replace('-', '月') + '日'
}
function msgItems(conv) {
  const out = []
  for (const m of (conv.messages || [])) out.push({ kind: 'msg', convId: conv.id, role: m.role, content: m.content, plan: m.plan })
  return out
}

// ---------- 恢复 / 构建消息流 ----------
async function restore() {
  restoring = true
  const r = await restoreOrSync()
  currentConvId.value = r.conversationId
  currentTitle.value = r.title || ''
  loggedIn.value = isLoggedIn()
  restoring = false
  await buildStream(r)
}

async function buildStream(r) {
  const token = getToken()
  if (!token) {
    // 未登录：仅当前会话（本地）
    flat.value = [
      { kind: 'divider', convId: null, title: r.title || '今天', date: todayStr(), isCurrent: true },
      ...(r.messages && r.messages.length
        ? r.messages.map((m) => ({ kind: 'msg', role: m.role, content: m.content, plan: m.plan }))
        : [{ kind: 'msg', role: 'assistant', content: welcomeText() }]),
    ]
    scrollToBottom()
    return
  }
  // 登录：最近一批会话（含当前）拼成统一流
  try {
    const list = await fetchConvoStream(token, { limit: 8 })
    const convs = [...list].reverse() // 旧 → 新
    const items = []
    for (const c of convs) {
      items.push({ kind: 'divider', convId: c.id, title: c.title, date: shortDate(c.updated_at), isCurrent: c.id === currentConvId.value })
      items.push(...msgItems(c))
    }
    if (!convs.some((c) => c.id === currentConvId.value) && r.messages && r.messages.length) {
      items.push({ kind: 'divider', convId: null, title: r.title || '今天', date: todayStr(), isCurrent: true })
      for (const m of r.messages) items.push({ kind: 'msg', role: m.role, content: m.content, plan: m.plan })
    }
    flat.value = items.length ? items : [
      { kind: 'divider', convId: null, title: '今天', date: todayStr(), isCurrent: true },
      { kind: 'msg', role: 'assistant', content: welcomeText() },
    ]
    oldestConvId = list.length ? list[list.length - 1].id : null
    olderEnded.value = list.length < 8
    olderLoadedAny.value = list.length > 0
  } catch (e) {
    flat.value = [
      { kind: 'divider', convId: null, title: '今天', date: todayStr(), isCurrent: true },
      { kind: 'msg', role: 'assistant', content: welcomeText() },
    ]
  }
  scrollToBottom()
}

// ---------- 向上加载更早历史 ----------
async function loadOlder() {
  const token = getToken()
  if (!token || olderLoading.value || olderEnded.value || !oldestConvId) return
  olderLoading.value = true
  const prevHeight = listEl.value ? listEl.value.scrollHeight : 0
  try {
    const list = await fetchConvoStream(token, { before_id: oldestConvId, limit: 8 })
    if (list.length) {
      const newItems = []
      for (const c of [...list].reverse()) {
        newItems.push({ kind: 'divider', convId: c.id, title: c.title, date: shortDate(c.updated_at), isCurrent: false })
        newItems.push(...msgItems(c))
      }
      flat.value = [...newItems, ...flat.value]
      oldestConvId = list[list.length - 1].id
      olderEnded.value = list.length < 8
      olderLoadedAny.value = true
      // 保持原视口位置：新内容追加在顶部，滚动条下移
      nextTick(() => {
        if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight - prevHeight
      })
    } else {
      olderEnded.value = true
    }
  } catch (e) { /* 静默 */ } finally {
    olderLoading.value = false
  }
}
function onListScroll(e) {
  const el = e.target
  if (el.scrollTop <= 50) loadOlder()
}

// ---------- 新对话（保留历史流在上方，重置当前会话段） ----------
function newConversation() {
  let cut = 0
  for (let i = flat.value.length - 1; i >= 0; i--) {
    if (flat.value[i].kind === 'divider' && flat.value[i].isCurrent) {
      cut = i
      break
    }
  }
  const head = flat.value.slice(0, cut)
  flat.value = [
    ...head,
    { kind: 'divider', convId: null, title: '今天', date: todayStr(), isCurrent: true },
    { kind: 'msg', role: 'assistant', content: welcomeText() },
  ]
  currentConvId.value = null
  currentTitle.value = ''
  scrollToBottom()
}

// ---------- 当前会话消息提取 / 自动保存 ----------
function currentMsgs() {
  let idx = -1
  for (let i = flat.value.length - 1; i >= 0; i--) {
    if (flat.value[i].kind === 'divider' && flat.value[i].isCurrent) { idx = i; break }
  }
  if (idx < 0) return []
  return flat.value.slice(idx + 1).filter((x) => x.kind === 'msg' && !x.loading)
    .map((m) => ({ role: m.role, content: m.content, plan: m.plan }))
}
function schedulePersist() {
  clearTimeout(persistTimer)
  persistTimer = setTimeout(persistNow, 800)
}
function persistNow() {
  persistChain = persistChain
    .catch(() => {})
    .then(() => doPersist())
  return persistChain
}
async function doPersist() {
  const msgs = currentMsgs()
  if (!msgs.some((m) => m.role === 'user')) return
  const title = currentTitle.value || deriveTitle(msgs)
  const token = getToken()
  if (!token) {
    saveLocalConvo({ title, messages: msgs })
    return
  }
  try {
    const conv = await persistConvo(token, {
      id: currentConvId.value || undefined,
      title,
      messages: msgs,
    })
    currentConvId.value = conv.id
    currentTitle.value = conv.title
  } catch (e) { /* 静默 */ }
}

// ---------- 对话 ----------
async function send(text) {
  const content = (text ?? draft.value).trim()
  if (!content || sending.value) return
  draft.value = ''
  flat.value.push({ kind: 'msg', role: 'user', content })
  const aiMsg = { kind: 'msg', role: 'assistant', content: '', loading: true }
  flat.value.push(aiMsg)
  sending.value = true
  scrollToBottom()
  try {
    // 只带当前会话消息，避免历史会话污染本轮意图解析
    const payload = currentMsgs().map((m) => ({ role: m.role, content: m.content }))
    const res = await chatPlan(payload)
    aiMsg.loading = false
    aiMsg.content = res.reply || '抱歉，我暂时没太听明白，能再说详细一点吗？'
    aiMsg.plan = res.ready && res.plan ? res.plan : null
    if (res.ready && res.plan) {
      reportTripIfLoggedIn({
        destination: res.plan.destination,
        days: res.plan.days,
        style: res.plan.style,
      })
      // 自动学习用户偏好（已登录用户）
      if (isLoggedIn()) {
        const planParams = {
          destination: res.plan.destination,
          days: res.plan.days,
          style: res.plan.style,
          pace: res.plan.pace,
          budget_level: res.plan.budget_level,
          group_type: res.plan.group_type,
          traffic_mode: res.plan.traffic_mode,
        }
        learnFromPlan(planParams).catch(() => { /* 静默，偏好学习失败不影响主流程 */ })
      }
    }
  } catch (e) {
    aiMsg.loading = false
    aiMsg.content = '生成失败：' + (e.message || '请确认后端服务已启动')
  } finally {
    sending.value = false
    scrollToBottom()
    persistNow() // 立即保存，避免切页丢失
  }
}

function openPlan(plan) {
  // 使用全局状态传递行程数据，不写入本地存储（避免新旧数据混淆）
  setCurrentPlan(plan)
  router.push({ name: 'plan', query: { id: plan.request_id } })
}

function scrollToBottom() {
  nextTick(() => {
    if (listEl.value) listEl.value.scrollTop = listEl.value.scrollHeight
  })
}

onMounted(() => {
  restore()
  window.addEventListener('travel:user-changed', restore)
})
onBeforeUnmount(() => {
  clearTimeout(persistTimer)
  persistNow()
  window.removeEventListener('travel:user-changed', restore)
})
</script>

<style scoped>
.chat-planner {
  display: flex;
  flex-direction: column;
}
.convo-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.convo-hint {
  font-size: 11px;
  color: var(--text-3);
  flex: 1;
}
.convo-btn {
  padding: 5px 11px;
  border-radius: 999px;
  background: #eef9f6;
  color: var(--primary-dark);
  font-size: 12px;
  font-weight: 600;
}
.convo-btn.ghost {
  background: #f0f4f3;
  color: var(--text-2);
}
.msg-list {
  max-height: 420px;
  min-height: 200px;
  overflow-y: auto;
  padding: 4px 2px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overscroll-behavior: contain;
}
.stream-tip {
  font-size: 11px;
  color: var(--text-3);
  text-align: center;
  padding: 6px 0;
}
.stream-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 14px 0 2px;
}
.stream-divider::before,
.stream-divider::after {
  content: '';
  height: 1px;
  width: 26px;
  background: var(--border);
}
.divider-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary-dark);
  max-width: 55%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.divider-date {
  font-size: 11px;
  color: var(--text-3);
}
.msg {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.msg.user {
  flex-direction: row-reverse;
}
.avatar {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.user-avatar {
  background: var(--primary);
  color: #fff;
}
.ai-avatar {
  background: #eef4f2;
  color: var(--primary-dark);
}
.bubble {
  max-width: 78%;
  padding: 10px 13px;
  border-radius: 14px;
  font-size: 14px;
  line-height: 1.55;
  word-break: break-word;
  white-space: pre-wrap;
}
.msg.user .bubble {
  background: var(--primary);
  color: #fff;
  border-top-right-radius: 4px;
}
.msg.assistant .bubble {
  background: #f3f7f5;
  color: var(--text);
  border-top-left-radius: 4px;
}
.text {
  white-space: pre-wrap;
}
.view-btn {
  display: block;
  width: 100%;
  margin-top: 10px;
  padding: 9px 0;
  border-radius: 10px;
  background: var(--gradient);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  text-align: center;
}
.typing {
  display: inline-flex;
  gap: 4px;
  align-items: center;
}
.typing i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--primary);
  animation: blink 1.2s infinite;
}
.typing i:nth-child(2) {
  animation-delay: 0.2s;
}
.typing i:nth-child(3) {
  animation-delay: 0.4s;
}
@keyframes blink {
  0%, 80%, 100% { opacity: 0.25; }
  40% { opacity: 1; }
}
.samples {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 2px 4px;
}
.samples-tip {
  font-size: 12px;
  color: var(--text-3);
}
.sample {
  text-align: left;
  padding: 9px 12px;
  border: 1.5px dashed var(--border);
  border-radius: 12px;
  background: #fbfdfc;
  color: var(--text);
  font-size: 13px;
}
.sample:active {
  background: #eef4f2;
  border-color: var(--primary);
}
.input-bar {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}
.chat-input {
  flex: 1;
  padding: 11px 13px;
  border: 1.5px solid var(--border);
  border-radius: 12px;
  font-size: 14px;
  background: #fbfdfc;
  color: var(--text);
}
.chat-input:focus {
  border-color: var(--primary);
}
.send-btn {
  padding: 0 18px;
  border-radius: 12px;
  background: var(--gradient);
  color: #fff;
  font-weight: 600;
  font-size: 14px;
  min-width: 64px;
}
.send-btn:disabled {
  opacity: 0.45;
}
.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: rot 0.8s linear infinite;
}
@keyframes rot {
  to { transform: rotate(360deg); }
}
</style>
