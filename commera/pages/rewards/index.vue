<script>
export const extension = { label: 'Top customers', icon: 'star', requires: 'Loyalty Ledger Entry', order: 2 }
</script>

<script setup>
import { computed, ref } from 'vue'
import { dayjs } from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow, ListRows } from 'frappe-ui/list'
import { EmptyState, ListPagination, ListSkeleton, useExtension, useMethodRead, usePage } from '@commera/admin'

const ROW_HEIGHT = 60

const { navigate } = useExtension()
usePage().setActions([{ label: 'View ledger', icon: 'award', onClick: () => navigate('loyalty') }])

const page = ref(1)
const pageSize = ref(20)

const customersRequest = useMethodRead('commera_loyalty.api.get_top_customers', {
  params: () => ({ start: (page.value - 1) * pageSize.value, page_length: pageSize.value }),
  refetch: true,
})

const rows = computed(() => customersRequest.data?.rows ?? [])
const total = computed(() => customersRequest.data?.total ?? 0)

const skeletonColumns = window.matchMedia('(max-width: 639.98px)').matches ? 2 : 4
</script>

<template>
  <div class="overflow-x-auto">
    <List
      class="max-sm:[--list-columns:minmax(0,1fr)_auto] sm:min-w-[44rem]"
      :row-height="ROW_HEIGHT"
      :columns="['1fr', '7rem', '9rem', '7rem']"
    >
      <ListHeader>
        <ListHeaderCell>Customer</ListHeaderCell>
        <ListHeaderCell class="max-sm:hidden">Entries</ListHeaderCell>
        <ListHeaderCell class="max-sm:hidden">Last activity</ListHeaderCell>
        <ListHeaderCell class="justify-end">Balance</ListHeaderCell>
      </ListHeader>

      <ListSkeleton v-if="customersRequest.loading && !rows.length" :columns="skeletonColumns" />

      <ListRows v-else :items="rows" row-key="customer" v-slot="{ item }">
        <ListRow :to="`/customers/${encodeURIComponent(item.customer)}`" :value="item.customer">
          <ListCell>
            <div class="min-w-0">
              <p class="truncate text-base text-ink-gray-8">{{ item.customer_name }}</p>
              <p class="truncate text-sm text-ink-gray-4 sm:hidden">{{ dayjs(item.last_activity).fromNow() }}</p>
            </div>
          </ListCell>
          <ListCell class="max-sm:hidden">
            <span class="text-base text-ink-gray-7 tabular-nums">{{ item.entries }}</span>
          </ListCell>
          <ListCell class="max-sm:hidden">
            <span class="text-sm text-ink-gray-5">{{ dayjs(item.last_activity).fromNow() }}</span>
          </ListCell>
          <ListCell>
            <span class="w-full text-right text-base text-ink-gray-8 tabular-nums">{{ item.balance }}</span>
          </ListCell>
        </ListRow>
      </ListRows>
    </List>
  </div>

  <ListPagination v-if="total" v-model:page="page" v-model:page-size="pageSize" :total="total" />

  <EmptyState
    v-if="!customersRequest.loading && !rows.length"
    icon="lucide-star"
    title="No customers with points yet"
    description="Customers show up here, highest balance first, once their first order is paid."
  />
</template>
