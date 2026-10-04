<script>
export const plugin = { label: 'Adjust loyalty points', icon: 'coins', requires: 'Loyalty Ledger Entry' }
</script>

<script setup>
import { computed, ref } from 'vue'
import { FormControl } from 'frappe-ui'
import { useAction, usePlugin, useMethodAction } from '@commera/admin'

const { record, toast } = usePlugin()
const action = useAction()

const points = ref('')
const note = ref('')

const pointsChange = computed(() => Number.parseInt(points.value, 10) || 0)

const adjustAction = useMethodAction('commera_loyalty.api.adjust_points')

action.setPrimary({
  label: () => (pointsChange.value < 0 ? 'Take away points' : 'Add points'),
  disabled: () => !pointsChange.value || !note.value.trim(),
})

action.onSubmit(async () => {
  const result = await adjustAction.submit({
    sales_order: record.value.name,
    points: pointsChange.value,
    note: note.value.trim(),
  })
  if (adjustAction.error) throw adjustAction.error
  toast.success(`Balance is now ${result.balance} points`)
  return { reload: true }
})
</script>

<template>
  <div class="space-y-4">
    <FormControl
      v-model="points"
      type="number"
      label="Points"
      description="A negative number takes points away."
      required
    />
    <FormControl v-model="note" type="textarea" label="Reason" placeholder="Why the balance is changing" required />
  </div>
</template>
