<template>
  <nav class="w-full bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
    <span class="text-blue-600 font-bold text-lg tracking-tight">XiaoZhi 猫咪饮水</span>
    <div class="flex items-center gap-6">
      <RouterLink
        v-for="link in links"
        :key="link.to"
        :to="link.to"
        class="text-sm text-gray-600 hover:text-blue-600 transition-colors"
        active-class="text-blue-600 font-semibold"
      >{{ link.label }}</RouterLink>
    </div>
    <DeviceStatus />
  </nav>
</template>

<script setup>
import DeviceStatus from './DeviceStatus.vue'

const links = [
  { to: '/', label: '主控台' },
  { to: '/sensor', label: '温湿度' },
  { to: '/meow', label: '猫叫检测' },
  { to: '/iot', label: '设备控制' },
  { to: '/water', label: '饮水管理' },
  { to: '/voice', label: '语音助手' },
  { to: '/settings', label: '设置' },
].filter((link) => link.to !== '/voice')
</script>
