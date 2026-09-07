<template>
  <div id="admin-app">
    <router-view />
  </div>
</template>

<script setup>
// 管理后台入口组件，只负责路由渲染
// 不包含App端的底部tabbar、移动端布局等
</script>

<style scoped>
#admin-app {
  width: 100%;
  min-height: 100vh;
}
</style>
