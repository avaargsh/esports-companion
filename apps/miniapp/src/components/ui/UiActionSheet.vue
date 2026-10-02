<script setup lang="ts">
import { computed } from "vue"
import TActionSheet from "@tdesign/uniapp/action-sheet/action-sheet.vue"

type UiActionSheetItem = {
  label: string
  description?: string
  disabled?: boolean
}

const props = withDefaults(defineProps<{
  visible: boolean
  items: UiActionSheetItem[]
  description?: string
  cancelText?: string
}>(), {
  description: "",
  cancelText: "取消"
})

const emit = defineEmits<{
  "update:visible": [visible: boolean]
  selected: [index: number]
  cancel: []
}>()

const tdesignItems = computed(() =>
  props.items.map(item => ({
    label: item.label,
    description: item.description,
    disabled: item.disabled
  }))
)

function detailOf(event: unknown): Record<string, unknown> {
  if (!event || typeof event !== "object") return {}
  const value = event as Record<string, unknown>
  const detail = value.detail
  return detail && typeof detail === "object"
    ? detail as Record<string, unknown>
    : value
}

function handleSelected(event: unknown) {
  const detail = detailOf(event)
  const index = Number(detail.index)
  if (Number.isInteger(index) && index >= 0) {
    emit("selected", index)
  }
  emit("update:visible", false)
}

function handleVisibleChange(event: unknown) {
  const detail = detailOf(event)
  if (typeof detail.visible === "boolean") {
    emit("update:visible", detail.visible)
  }
}

function handleCancel() {
  emit("update:visible", false)
  emit("cancel")
}
</script>

<template>
  <TActionSheet
    :visible="visible"
    :items="tdesignItems"
    :description="description"
    :cancel-text="cancelText"
    @selected="handleSelected"
    @visible-change="handleVisibleChange"
    @cancel="handleCancel"
  />
</template>
