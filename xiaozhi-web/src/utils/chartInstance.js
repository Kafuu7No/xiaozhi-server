export function isChartBoundToElement(chart, element) {
  return !!chart && !!element && chart.getDom?.() === element
}
