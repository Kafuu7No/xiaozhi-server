<template>
  <div class="app-card overflow-hidden">
    <div class="overflow-x-auto">
      <table class="table table-sm w-full">
        <thead>
          <tr>
            <th>时间</th>
            <th>识别把握度</th>
            <th>识别结果</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="event in events"
            :key="event.id ?? event.ts ?? event.recorded_at"
            class="hover:bg-base-200"
          >
            <td class="text-base-content/50 text-xs">{{ formatTime(event) }}</td>
            <td>
              <div class="flex items-center gap-2">
                <progress
                  class="progress w-16"
                  :class="event.is_cat ? 'progress-primary' : 'progress-success'"
                  :value="event.score * 100"
                  max="100"
                />
                <span class="text-xs text-base-content/50">{{ (event.score * 100).toFixed(0) }}%</span>
              </div>
            </td>
            <td>
              <span v-if="event.is_cat" class="badge badge-primary badge-sm">猫叫</span>
              <span v-else class="badge badge-success badge-sm">噪声</span>
            </td>
          </tr>
          <tr v-if="!events.length">
            <td colspan="3" class="py-6 text-center text-base-content/30">暂无事件</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
defineProps({ events: { type: Array, default: () => [] } })

function formatTime(event) {
  if (typeof event?.ts === 'number') {
    return new Date(event.ts).toLocaleString('zh-CN', { hour12: false }).slice(0, 16)
  }
  return event?.recorded_at ? event.recorded_at.replace('T', ' ').slice(0, 16) : '--'
}
</script>
