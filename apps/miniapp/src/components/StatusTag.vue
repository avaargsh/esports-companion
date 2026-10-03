<script setup lang="ts">
import { computed } from "vue"

import UiBadge from "./ui/UiBadge.vue"
import type { OrderStatus } from "../types/domain"
import { orderStatusMeta, type OrderRole } from "../utils/order"

type BadgeTone = "neutral" | "brand" | "success" | "warning" | "danger"

const props = withDefaults(
  defineProps<{ status: OrderStatus|string; role?: OrderRole }>(),
  { role: "CUSTOMER" }
)

const meta = computed(() => orderStatusMeta(props.status, props.role))
const tone = computed<BadgeTone>(() =>
  meta.value.tone === "primary" ? "brand" : meta.value.tone
)
</script>

<template>
  <UiBadge :tone="tone" dot>
    {{ meta.label }}
  </UiBadge>
</template>
