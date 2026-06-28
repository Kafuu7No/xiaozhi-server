import test from 'node:test'
import assert from 'node:assert/strict'

import { isChartBoundToElement } from './chartInstance.js'

test('detects when an ECharts instance belongs to a stale DOM node', () => {
  const oldElement = {}
  const newElement = {}
  const chart = {
    getDom: () => oldElement,
  }

  assert.equal(isChartBoundToElement(chart, oldElement), true)
  assert.equal(isChartBoundToElement(chart, newElement), false)
})

test('treats missing chart or element as unbound', () => {
  const element = {}

  assert.equal(isChartBoundToElement(null, element), false)
  assert.equal(isChartBoundToElement({ getDom: () => element }, null), false)
})
