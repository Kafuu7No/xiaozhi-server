import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { CONTROL_MODE, getModeMenuItems } from './router/modeRouting.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

function readSource(relativePath) {
  return readFileSync(join(__dirname, relativePath), 'utf8')
}

function templateOnly(source) {
  return source
    .replace(/<script[\s\S]*?<\/script>/g, '')
    .replace(/<style[\s\S]*?<\/style>/g, '')
    .replace(/\{\{[\s\S]*?\}\}/g, '')
    .replace(/:[\w-]+="[^"]*"/g, '')
}

test('uses plain-language labels for ordinary users instead of technical jargon', () => {
  const controlLabels = getModeMenuItems(CONTROL_MODE).map((item) => item.label)
  assert.ok(controlLabels.includes('设备控制'))
  assert.ok(!controlLabels.some((label) => /IoT/i.test(label)))

  const files = [
    'views/DashboardView.vue',
    'views/SensorView.vue',
    'views/MeowView.vue',
    'views/WaterView.vue',
    'views/SettingsView.vue',
    'views/IotControlView.vue',
    'components/BottomNav.vue',
    'components/IotDeviceCard.vue',
    'components/MeowEventList.vue',
    'components/NavBar.vue',
  ]
  const visibleCopy = files.map((file) => templateOnly(readSource(file))).join('\n')

  for (const jargon of ['score', '置信度', '检测阈值', '诊断回退', '原始数据', '立即开泵']) {
    assert.ok(!visibleCopy.includes(jargon), `unexpected user-facing jargon: ${jargon}`)
  }

  for (const plainCopy of ['识别把握度', '保存门槛', '临时诊断数据', '详细记录', '立即出水']) {
    assert.ok(visibleCopy.includes(plainCopy), `missing plain-language copy: ${plainCopy}`)
  }

  assert.ok(readSource('views/SettingsView.vue').includes('v-model.number="settings.meowMinConfidence"'))
  assert.ok(readSource('views/SettingsView.vue').includes('meowMinConfidence: 0.4'))
  const waterView = readSource('views/WaterView.vue')
  assert.ok(waterView.includes('确认删除计划'))
  assert.ok(waterView.includes('role="dialog"'))
  assert.ok(waterView.includes('aria-modal="true"'))
  assert.ok(!/minConfidenceBucketLabel|60-70%|70-80%/.test(readSource('views/MeowView.vue')))
})
