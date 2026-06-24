<template>
  <div class="chart-wrapper">
    <v-chart :option="normalizedOption" autoresize style="height: 350px; width: 100%" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { BarChart, LineChart, PieChart, ScatterChart, RadarChart, TreeChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([
  BarChart, LineChart, PieChart, ScatterChart, RadarChart, TreeChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, DatasetComponent, TransformComponent,
  CanvasRenderer,
])

const props = defineProps({
  option: { type: Object, required: true },
})

const normalizedOption = computed(() => {
  if (!props.option || typeof props.option !== 'object') return {}
  if (props.option.option && typeof props.option.option === 'object') {
    return props.option.option
  }
  return props.option
})
</script>

<style scoped>
.chart-wrapper { margin: 12px 0; border: 1px solid #e4e7ed; border-radius: 8px; padding: 12px; background: #fff; }
</style>
