<template>
  <nav class="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 flex justify-around z-50">
    <RouterLink
      v-for="link in links"
      :key="link.to"
      :to="link.to"
      class="flex flex-col items-center py-2 px-3 text-xs text-gray-500 hover:text-blue-600 transition-colors"
      active-class="text-blue-600"
    >
      <span class="text-xl">{{ link.icon }}</span>
      <span>{{ link.label }}</span>
    </RouterLink>
  </nav>
</template>

<script setup>
const links = [
  { to: '/', label: '主控台', icon: '⌂' },
  { to: '/sensor', label: '温湿度', icon: '℃' },
  { to: '/meow', label: '猫叫', icon: '猫' },
  { to: '/iot', label: '设备', icon: '▣' },
  { to: '/water', label: '饮水', icon: '水' },
  { to: '/voice', label: '语音', icon: '🎤' },
].filter((link) => link.to !== '/voice')
</script>
