/**
 * 高德 JS API 共享加载工具。
 * 地图渲染（MapView）等组件共用，避免重复注入脚本。
 */
const AMAP_KEY = import.meta.env.VITE_AMAP_WEB_KEY || ''
const AMAP_SECURITY_CODE = import.meta.env.VITE_AMAP_SECURITY_CODE || ''

let amapPromise = null

/** 加载高德 JS API，返回 AMap 对象（失败返回 null） */
export function loadAmap() {
  if (!AMAP_KEY) return Promise.resolve(null)
  if (window.AMap) return Promise.resolve(window.AMap)
  if (amapPromise) return amapPromise
  if (AMAP_SECURITY_CODE) {
    window._AMapSecurityConfig = { securityJsCode: AMAP_SECURITY_CODE }
  }
  amapPromise = new Promise((resolve) => {
    const s = document.createElement('script')
    s.src = `https://webapi.amap.com/maps?v=2.0&key=${AMAP_KEY}`
    s.onload = () => resolve(window.AMap || null)
    s.onerror = () => resolve(null)
    document.head.appendChild(s)
  })
  return amapPromise
}
