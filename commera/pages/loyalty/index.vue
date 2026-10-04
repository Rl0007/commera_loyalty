<script>
export const plugin = { label: 'Ledger', icon: 'award', requires: 'Loyalty Ledger Entry', order: 1 }
</script>

<script setup>
import { computed, ref, watch } from 'vue'
import { Select, Skeleton } from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import {
  EmptyState,
  ListPagination,
  ListSkeleton,
  shortDate,
  usePlugin,
  useMethodRead,
  usePage,
} from '@commera/admin'

const ALL_CUSTOMERS = 'all'
const ROW_HEIGHT = 60

const { query, navigate } = usePlugin()

const customer = computed({
  get: () => query.value.customer || ALL_CUSTOMERS,
  set: (value) =>
    navigate(value === ALL_CUSTOMERS ? 'loyalty' : `loyalty?customer=${encodeURIComponent(value)}`),
})

const pageHeader = usePage()
pageHeader.setTitle('Loyalty ledger')
pageHeader.setBreadcrumbs(() =>
  customer.value === ALL_CUSTOMERS ? [] : [{ label: 'Loyalty ledger', to: 'loyalty' }, { label: customer.value }],
)
pageHeader.setActions([{ label: 'Top customers', icon: 'star', onClick: () => navigate('rewards') }])

const page = ref(1)
const pageSize = ref(20)

const ledgerRequest = useMethodRead('commera_loyalty.api.get_ledger', {
  params: () => ({
    customer: customer.value === ALL_CUSTOMERS ? undefined : customer.value,
    start: (page.value - 1) * pageSize.value,
    page_length: pageSize.value,
  }),
  refetch: true,
})

watch(customer, () => (page.value = 1))

const ledger = computed(() => ledgerRequest.data)
const rows = computed(() => ledger.value?.rows ?? [])
const total = computed(() => ledger.value?.total ?? 0)

// The customer list comes back with every page, so it is kept once rather than flickering on each fetch.
const customerOptions = ref([{ label: 'All customers', value: ALL_CUSTOMERS }])
watch(
  () => ledger.value?.customers,
  (customers) => {
    if (!customers) return
    customerOptions.value = [
      { label: 'All customers', value: ALL_CUSTOMERS },
      ...customers.map((name) => ({ label: name, value: name })),
    ]
  },
)

const stats = computed(() => {
  const issued = ledger.value?.issued ?? 0
  const reversed = ledger.value?.reversed ?? 0
  return [
    customer.value === ALL_CUSTOMERS
      ? { label: 'Outstanding', value: issued - reversed, note: 'Across every customer' }
      : { label: 'Balance', value: ledger.value?.balance ?? 0, note: customer.value },
    { label: 'Issued', value: issued, note: 'Points earned on paid orders' },
    { label: 'Reversed', value: reversed, note: 'Taken back on refunds and cancellations' },
    { label: 'Entries', value: total.value, note: 'Ledger rows' },
  ]
})

const skeletonColumns = window.matchMedia('(max-width: 639.98px)').matches ? 2 : 5

const signed = (points) => (points > 0 ? `+${points}` : `${points}`)
</script>

<template>
  <div class="grid grid-cols-2 rounded-5 border border-outline-gray-1 sm:grid-cols-4 sm:divide-x sm:divide-outline-gray-2">
    <div v-for="stat in stats" :key="stat.label" class="px-4 py-3.5">
      <Skeleton v-if="ledgerRequest.loading && !ledger" class="h-20 w-full rounded-4" />
      <template v-else>
        <p class="text-sm text-ink-gray-5">{{ stat.label }}</p>
        <p class="mt-1 text-2xl text-ink-gray-9 tabular-nums">{{ stat.value }}</p>
        <p class="mt-1 truncate text-sm text-ink-gray-5">{{ stat.note }}</p>
      </template>
    </div>
  </div>

  <div class="mt-5 flex flex-wrap items-center gap-2">
    <Select v-model="customer" :options="customerOptions" />
  </div>

  <div class="mt-3 overflow-x-auto">
    <List
      class="max-sm:[--list-columns:minmax(0,1fr)_auto] sm:min-w-[44rem]"
      :row-height="ROW_HEIGHT"
      :columns="['1fr', '7rem', '11rem', '10rem', '6rem']"
    >
      <ListHeader>
        <ListHeaderCell>Customer</ListHeaderCell>
        <ListHeaderCell class="max-sm:hidden">Date</ListHeaderCell>
        <ListHeaderCell class="max-sm:hidden">Order</ListHeaderCell>
        <ListHeaderCell class="max-sm:hidden">Reason</ListHeaderCell>
        <ListHeaderCell class="justify-end">Points</ListHeaderCell>
      </ListHeader>

      <ListSkeleton v-if="ledgerRequest.loading && !rows.length" :columns="skeletonColumns" />

      <ListRows v-else :items="rows" row-key="name" v-slot="{ item }">
        <ListRow :to="`/orders/${item.sales_order}`" :value="item.name">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ item.customer }}</p>
              <p class="truncate text-sm text-ink-gray-4 sm:hidden">{{ item.reason }}</p>
            </div>
          </ListCell>
          <ListCell class="max-sm:hidden">
            <span class="text-base text-ink-gray-5">{{ shortDate(item.creation) }}</span>
          </ListCell>
          <ListCell class="max-sm:hidden">
            <span class="truncate text-base text-ink-gray-7 tabular-nums">{{ item.sales_order }}</span>
          </ListCell>
          <ListCell class="max-sm:hidden">
            <span class="truncate text-base text-ink-gray-7">{{ item.reason }}</span>
          </ListCell>
          <ListCell>
            <span class="w-full text-right text-base text-ink-gray-8 tabular-nums">{{ signed(item.points) }}</span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>

  <ListPagination v-if="total" v-model:page="page" v-model:page-size="pageSize" :total="total" />

  <EmptyState
    v-if="!ledgerRequest.loading && !rows.length"
    icon="lucide-award"
    title="No points issued yet"
    description="A customer earns points the moment their order is paid, and they show up here."
    :filtered="customer !== ALL_CUSTOMERS"
    filtered-title="No points for this customer"
    filtered-description="Pick another customer, or all customers."
  />
</template>
