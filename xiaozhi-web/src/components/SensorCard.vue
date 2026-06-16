<template>
  <div class="card bg-base-100 border border-base-300">
    <div class="card-body p-5 gap-1">
      <span class="text-xs text-base-content/40 uppercase tracking-wide">{{ label }}</span>
      <span class="text-4xl font-bold" :class="color">
        {{ value !== null ? value : '--' }}<span class="text-xl font-normal ml-1">{{ unit }}</span>
      </span>
      <span class="text-xs text-base-content/40">{{ subtitle }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({
  label: String,
  value: { type: [Number, String], default: null },
  unit: String,
  color: { type: String, default: 'text-primary' },
  subtitle: { type: String, default: '' },
})
</script>
