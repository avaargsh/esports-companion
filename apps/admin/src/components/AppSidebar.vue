<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import rootsLogo from "../assets/roots-logo.png"
import { adminRequest } from "../api"

type AdminTab = "dashboard" | "orders" | "players" | "finance" | "config"

type NavItem = {
  key: AdminTab
  label: string
}

type MenuIcon = {
  key: AdminTab
  label: string
  iconUrl: string
  sortOrder: number
}

const props = defineProps<{
  items: NavItem[]
  active: AdminTab
  authLabel: string
  canLogout: boolean
}>()

const emit = defineEmits<{
  select: [value: AdminTab]
  logout: []
}>()

const collapsed = ref(false)
const icons = ref<MenuIcon[]>([])
const failedIcons = ref<Record<string, boolean>>({})

const iconByKey = computed(() => {
  const map = new Map<AdminTab, MenuIcon>()
  icons.value.forEach((item) => map.set(item.key, item))
  return map
})

function iconFor(item: NavItem) {
  return iconByKey.value.get(item.key)?.iconUrl || ""
}

function labelFor(item: NavItem) {
  return iconByKey.value.get(item.key)?.label || item.label
}

function markIconFailed(key: AdminTab) {
  failedIcons.value = { ...failedIcons.value, [key]: true }
}

async function loadMenuIcons() {
  try {
    icons.value = await adminRequest<MenuIcon[]>("/admin/menu-icons")
  } catch {
    icons.value = []
  }
}

onMounted(loadMenuIcons)
</script>

<template>
  <aside class="sidebar" :class="{ collapsed }">
    <div class="brand">
      <img class="brand-logo" :src="rootsLogo" alt="若水电竞" />
      <div class="brand-copy">
        <strong>若水电竞</strong>
        <span>Marketplace Admin</span>
      </div>
      <button class="collapse" type="button" :aria-label="collapsed ? '展开导航' : '收起导航'" @click="collapsed = !collapsed">
        <span></span>
        <span></span>
      </button>
    </div>

    <nav>
      <button
        v-for="item in items"
        :key="item.key"
        :class="{ active: active === item.key }"
        type="button"
        @click="emit('select', item.key)"
      >
        <span class="nav-icon">
          <img
            v-if="iconFor(item) && !failedIcons[item.key]"
            :src="iconFor(item)"
            :alt="labelFor(item)"
            @error="markIconFailed(item.key)"
          />
          <span v-else>{{ labelFor(item).slice(0, 1) }}</span>
        </span>
        <span class="nav-label">{{ labelFor(item) }}</span>
      </button>
    </nav>

    <div class="sidebar-foot">
      <span class="dot"></span>
      <span class="auth-label">{{ authLabel }}</span>
      <button v-if="canLogout" class="logout" type="button" @click="emit('logout')">退出</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar{position:sticky;top:0;height:100vh;width:246px;padding:24px 18px;background:#12121a;color:#fff;display:flex;flex-direction:column;transition:width .2s ease,padding .2s ease;border-right:1px solid rgba(255,255,255,.06)}
.sidebar.collapsed{width:82px;padding-left:14px;padding-right:14px}.brand{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;padding:4px 4px 30px}.brand-logo{width:94px;height:38px;object-fit:contain;transition:width .2s ease}.brand-copy strong,.brand-copy span{display:block}.brand-copy strong{font-size:15px}.brand-copy span{margin-top:3px;color:#858591;font-size:11px}.collapse{width:30px;height:30px;border:1px solid rgba(255,255,255,.08);border-radius:10px;background:#1f1e29;display:grid;place-items:center;gap:3px;cursor:pointer}.collapse span{display:block;width:12px;height:2px;border-radius:999px;background:#a5a3b3}.sidebar.collapsed .brand{grid-template-columns:1fr}.sidebar.collapsed .brand-logo{width:48px}.sidebar.collapsed .brand-copy{display:none}.sidebar.collapsed .collapse{margin:auto;transform:rotate(90deg)}
nav{display:grid;gap:8px}nav button{width:100%;border:0;padding:12px 13px;border-radius:14px;background:transparent;color:#a6a5b1;text-align:left;cursor:pointer;display:flex;align-items:center;gap:10px;transition:background .16s ease,color .16s ease}nav button:hover{background:#1e1d28;color:#fff}nav button.active{background:#282735;color:#fff;box-shadow:inset 3px 0 0 #7c3aed}.nav-icon{display:inline-grid;width:32px;height:32px;place-items:center;flex:none;border-radius:10px;background:#22212d;overflow:hidden}.nav-icon img{width:19px;height:19px;object-fit:contain}.nav-icon span{font-size:13px;font-weight:800;color:#d8d4ff}nav button.active .nav-icon{background:#6c5ce7}.nav-label{white-space:nowrap;font-size:14px}.sidebar.collapsed .nav-label{display:none}.sidebar.collapsed nav button{justify-content:center;padding-left:0;padding-right:0}.sidebar-foot{margin-top:auto;min-height:46px;padding:14px;border-radius:15px;background:#1d1c27;color:#9c9ca8;font-size:12px;display:flex;align-items:center;gap:8px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;flex:none}.auth-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.logout{margin-left:auto;border:0;padding:0;background:transparent;color:#c7c5d1;cursor:pointer;font-size:11px}.sidebar.collapsed .auth-label,.sidebar.collapsed .logout{display:none}.sidebar.collapsed .sidebar-foot{justify-content:center;padding-left:0;padding-right:0}
</style>
