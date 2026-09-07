<template>
  <div class="panel">
    <h2>⚙️ 系统配置</h2>
    <p class="tip">缓存 TTL 与品牌文案管理（M9）—— 保存后立即生效</p>

    <div v-if="form" class="config-form">
      <h3>品牌文案（C 端首页展示）</h3>
      <label>
        <span>品牌口号 Slogan</span>
        <input v-model="form.brand_slogan" placeholder="世界在等你，去见山海！" />
      </label>
      <label>
        <span>Hero 文案</span>
        <input v-model="form.brand_hero" placeholder="用对话生成你的专属旅行计划" />
      </label>
      <label>
        <span>底部文案</span>
        <input v-model="form.brand_footer" placeholder="去见山海 · 激发行走天下的勇气" />
      </label>

      <h3>缓存 TTL</h3>
      <div class="ttl-grid">
        <label>
          <span>Geo（天）</span>
          <input v-model="form.ttl_geo_days" type="number" min="1" />
        </label>
        <label>
          <span>POI（天）</span>
          <input v-model="form.ttl_poi_days" type="number" min="1" />
        </label>
        <label>
          <span>Route（分钟）</span>
          <input v-model="form.ttl_route_min" type="number" min="1" />
        </label>
        <label>
          <span>Weather（小时）</span>
          <input v-model="form.ttl_weather_h" type="number" min="1" />
        </label>
      </div>

      <div class="actions">
        <button class="primary" @click="save" :disabled="saving">
          {{ saving ? '保存中…' : '保存配置' }}
        </button>
        <button class="ghost" @click="load">重置</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { adminRequest } from '../../../api'

const props = defineProps({ token: String })
const form = ref(null)
const saving = ref(false)

async function load() {
  form.value = await adminRequest('/config', {}, props.token)
}

async function save() {
  saving.value = true
  try {
    await adminRequest('/config', {
      method: 'PUT',
      body: JSON.stringify({
        brand_slogan: form.value.brand_slogan,
        brand_hero: form.value.brand_hero,
        brand_footer: form.value.brand_footer,
        ttl_geo_days: String(form.value.ttl_geo_days),
        ttl_poi_days: String(form.value.ttl_poi_days),
        ttl_route_min: String(form.value.ttl_route_min),
        ttl_weather_h: String(form.value.ttl_weather_h),
      }),
    }, props.token)
    alert('配置已保存，立即生效')
  } catch (e) {
    alert('保存失败：' + e.message)
  } finally {
    saving.value = false
  }
}
onMounted(load)
</script>

<style scoped>
.config-form {
  max-width: 560px;
  background: #fff;
  border: 1px solid #e6e9ef;
  border-radius: 12px;
  padding: 20px 22px;
}
h3 {
  margin: 6px 0 12px;
  font-size: 15px;
}
label {
  display: block;
  margin-bottom: 12px;
}
label span {
  display: block;
  font-size: 12px;
  color: #7a8494;
  margin-bottom: 5px;
}
input {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #dfe3ea;
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}
.ttl-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 12px;
}
.actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.primary {
  padding: 9px 20px;
  background: #1a9e5c;
  color: #fff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
}
.ghost {
  padding: 9px 18px;
  background: #fff;
  color: #1a2a3a;
  border: 1px solid #ccd2dc;
  border-radius: 8px;
  cursor: pointer;
}
</style>
