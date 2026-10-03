<script>
export const extension = { label: 'Loyalty points', requires: 'Loyalty Ledger Entry' }
</script>

<script setup>
import { Button, Skeleton } from 'frappe-ui'
import { useExtension, useMethodRead } from '@commera/admin'

const { record, navigate } = useExtension()

const pointsRequest = useMethodRead('commera_loyalty.loyalty.get_points', {
  params: () => ({ customer: record.value.name }),
})

function openLedger() {
  navigate(`loyalty?customer=${encodeURIComponent(record.value.name)}`)
}
</script>

<template>
  <Skeleton v-if="pointsRequest.loading && pointsRequest.data == null" class="h-8 w-24 rounded-4" />
  <template v-else>
    <p class="text-2xl text-ink-gray-9 tabular-nums">{{ pointsRequest.data ?? 0 }}</p>
    <p class="mt-1 text-sm text-ink-gray-5">Earned on paid orders, less refunds and adjustments.</p>
  </template>
  <Button class="mt-3" label="View ledger" icon-left="lucide-award" @click="openLedger" />
</template>
