<script>
export const extension = {
  label: 'Loyalty points',
  requires: 'Loyalty Ledger Entry',
  condition: 'commera_loyalty.conditions.has_ledger_entries',
}
</script>

<script setup>
import { computed } from 'vue'
import { Skeleton } from 'frappe-ui'
import { shortDate, useExtension, useMethodRead } from '@commera/admin'

const { record } = useExtension()

const pointsRequest = useMethodRead('commera_loyalty.api.get_order_points', {
  params: () => ({ sales_order: record.value.name }),
})

const points = computed(() => pointsRequest.data)

const signed = (value) => (value > 0 ? `+${value}` : `${value}`)
</script>

<template>
  <Skeleton v-if="pointsRequest.loading && !points" class="h-16 w-full rounded-4" />
  <template v-else-if="points">
    <div class="grid grid-cols-2 gap-3">
      <div>
        <p class="text-sm text-ink-gray-5">Earned</p>
        <p class="mt-1 text-xl text-ink-gray-9 tabular-nums">{{ points.earned }}</p>
      </div>
      <div>
        <p class="text-sm text-ink-gray-5">Reversed</p>
        <p class="mt-1 text-xl text-ink-gray-9 tabular-nums">{{ points.reversed }}</p>
      </div>
    </div>
    <div class="mt-3 divide-y divide-outline-gray-1 border-t border-outline-gray-1">
      <div v-for="row in points.rows" :key="row.name" class="flex items-start justify-between gap-3 py-2">
        <div class="min-w-0">
          <p class="truncate text-base text-ink-gray-8">{{ row.reason }}</p>
          <p class="truncate text-sm text-ink-gray-5">{{ row.note || shortDate(row.creation) }}</p>
        </div>
        <span class="text-base text-ink-gray-8 tabular-nums">{{ signed(row.points) }}</span>
      </div>
    </div>
  </template>
</template>
