<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import rootsLogo from "../assets/roots-logo.png"
import { adminRequest } from "../api"
import { isAdminSection, type AdminSection } from "../navigation"

type NavItem = {
  key: string
  label: string
  iconUrl: string
  children: Array<{ label: string; target: AdminSection }>
}

type MenuIcon = {
  key: string
  label: string
  iconUrl: string
  sortOrder: number
}

const props = defineProps<{
  items: NavItem[]
  active: AdminSection
  authLabel: string
  canLogout: boolean
}>()

const emit = defineEmits<{
  select: [value: AdminSection]
  logout: []
}>()

const collapsed = ref(false)
const icons = ref<MenuIcon[]>([])
const failedIcons = ref<Record<string, boolean>>({})

const iconByKey = computed(() => {
  const map = new Map<string, MenuIcon>()
  icons.value.forEach((item) => map.set(item.key, item))
  return map
})

function isActive(item: NavItem) {
  if (isAdminSection(item.key) && props.active === item.key) return true
  return item.children.some(child => child.target === props.active)
}

function iconFor(item: NavItem) {
  return iconByKey.value.get(item.key)?.iconUrl || item.iconUrl
}

function labelFor(item: NavItem) {
  return iconByKey.value.get(item.key)?.label || item.label
}

function selectItem(item: NavItem) {
  const target = isAdminSection(item.key) ? item.key : item.children[0]?.target
  if (target) emit("select", target)
}

function markIconFailed(key: string) {
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
      <div
        v-for="item in items"
        :key="item.key"
        class="nav-group"
        :class="{ active: isActive(item) }"
      >
        <button type="button" class="nav-parent" @click="selectItem(item)">
          <span class="nav-icon">
            <img
              v-if="iconFor(item) && !failedIcons[item.key]"
              :src="iconFor(item)"
              :alt="labelFor(item)"
              @error="markIconFailed(item.key)"
            />
          </span>
          <span class="nav-label">{{ labelFor(item) }}</span>
        </button>
        <div v-if="!collapsed" class="nav-children">
          <button
            v-for="child in item.children"
            :key="item.key + child.label"
            type="button"
            :class="{ current: active === child.target && isActive(item) }"
            @click="emit('select', child.target)"
          >
            {{ child.label }}
          </button>
        </div>
      </div>
    </nav>

    <div class="sidebar-foot">
      <span class="dot"></span>
      <span class="auth-label">{{ authLabel }}</span>
      <button v-if="canLogout" class="logout" type="button" @click="emit('logout')">退出</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar{position:sticky;top:0;height:100vh;width:286px;padding:24px 18px;background:#0f0f10;color:#fff;display:flex;flex-direction:column;transition:width .2s ease,padding .2s ease;border-right:1px solid rgba(0,0,0,.08);box-shadow:14px 0 40px rgba(0,0,0,.18);overflow:auto}.sidebar.collapsed{width:88px;padding-left:14px;padding-right:14px}.brand{display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:12px;padding:4px 4px 26px}.brand-logo{width:96px;height:39px;object-fit:contain;transition:width .2s ease}.brand-copy strong,.brand-copy span{display:block}.brand-copy strong{font-size:15px;color:#fff}.brand-copy span{margin-top:3px;color:#d1d5db;font-size:11px}.collapse{width:30px;height:30px;border:1px solid rgba(0,0,0,.10);border-radius:10px;background:#f3f4f6;display:grid;place-items:center;gap:3px;cursor:pointer}.collapse span{display:block;width:12px;height:2px;border-radius:999px;background:#111827}.sidebar.collapsed .brand{grid-template-columns:1fr}.sidebar.collapsed .brand-logo{width:52px}.sidebar.collapsed .brand-copy{display:none}.sidebar.collapsed .collapse{margin:auto;transform:rotate(90deg)}nav{display:grid;gap:8px}.nav-group{position:relative;border:1px solid transparent;border-radius:16px;transition:background .16s ease,border-color .16s ease}.nav-group::before{content:"";position:absolute;left:-1px;top:12px;bottom:12px;width:3px;border-radius:999px;background:transparent}.nav-group.active{border-color:rgba(255,255,255,.22);background:rgba(255,255,255,.12)}.nav-group.active::before{background:#fff;box-shadow:0 0 16px rgba(255,255,255,.35)}.nav-parent{width:100%;border:0;padding:12px 13px;border-radius:15px;background:transparent;color:#6b7280;text-align:left;cursor:pointer;display:flex;align-items:center;gap:10px;transition:color .16s ease}.nav-group:hover .nav-parent,.nav-group.active .nav-parent{color:#fff}.nav-icon{display:inline-grid;width:32px;height:32px;place-items:center;flex:none;border-radius:10px;background:#f3f4f6;overflow:hidden}.nav-icon img{width:21px;height:21px;object-fit:contain}.nav-label{white-space:nowrap;font-size:14px;font-weight:760}.nav-children{display:grid;gap:2px;padding:0 10px 10px 55px}.nav-children button{border:0;background:transparent;color:#6b7280;text-align:left;cursor:pointer;font-size:12px;line-height:1.2;padding:6px 0}.nav-children button.current{color:#fff}.sidebar.collapsed .nav-label,.sidebar.collapsed .nav-children{display:none}.sidebar.collapsed .nav-parent{justify-content:center;padding-left:0;padding-right:0}.sidebar-foot{margin-top:auto;min-height:46px;padding:14px;border:1px solid rgba(255,255,255,.14);border-radius:15px;background:#1f2937;color:#e5e7eb;font-size:12px;display:flex;align-items:center;gap:8px}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#fff;box-shadow:0 0 14px rgba(255,255,255,.5);flex:none}.auth-label{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.logout{margin-left:auto;border:0;padding:0;background:transparent;color:#fff;cursor:pointer;font-size:11px}.sidebar.collapsed .auth-label,.sidebar.collapsed .logout{display:none}.sidebar.collapsed .sidebar-foot{justify-content:center;padding-left:0;padding-right:0}
</style>
