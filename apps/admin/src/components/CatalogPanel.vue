<script setup lang="ts">
import { onMounted, ref } from "vue"

import { adminRequest } from "../api"

type CatalogGame = {
  id: string
  code: string
  name: string
  iconUrl?: string | null
  status: string
  sortOrder: number
}

type CatalogSku = {
  id: string
  gameId: string
  gameName: string
  name: string
  serviceType: string
  unit: string
  durationMinutes: number
  price: number
  platformFeeRate: number
  status: string
}

const games = ref<CatalogGame[]>([])
const skus = ref<CatalogSku[]>([])
const loading = ref(false)
const error = ref("")

const gameCode = ref("")
const gameName = ref("")
const skuGameId = ref("")
const skuName = ref("")
const skuDuration = ref(60)
const skuPriceYuan = ref(30)

async function load() {
  loading.value = true
  error.value = ""
  try {
    const [gameRows, skuRows] = await Promise.all([
      adminRequest<CatalogGame[]>("/admin/catalog/games"),
      adminRequest<CatalogSku[]>("/admin/catalog/skus")
    ])
    games.value = gameRows
    skus.value = skuRows
    if (!skuGameId.value && games.value.length) {
      skuGameId.value = games.value[0].id
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "配置加载失败"
  } finally {
    loading.value = false
  }
}

async function createGame() {
  if (!gameCode.value.trim() || !gameName.value.trim()) return
  try {
    await adminRequest("/admin/catalog/games", {
      method: "POST",
      body: {
        code: gameCode.value.trim(),
        name: gameName.value.trim(),
        sort_order: games.value.length
      }
    })
    gameCode.value = ""
    gameName.value = ""
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "新增游戏失败"
  }
}

async function toggleGame(game: CatalogGame) {
  try {
    await adminRequest(`/admin/catalog/games/${game.id}`, {
      method: "PATCH",
      body: { status: game.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "更新游戏失败"
  }
}

async function createSku() {
  if (!skuGameId.value || !skuName.value.trim()) return
  try {
    await adminRequest("/admin/catalog/skus", {
      method: "POST",
      body: {
        game_id: skuGameId.value,
        name: skuName.value.trim(),
        service_type: "ENTERTAINMENT",
        unit: "SESSION",
        duration_minutes: Number(skuDuration.value),
        price: Math.round(Number(skuPriceYuan.value) * 100),
        platform_fee_rate: "0.2000",
        status: "ACTIVE",
        config_json: {}
      }
    })
    skuName.value = ""
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "新增服务套餐失败"
  }
}

async function toggleSku(sku: CatalogSku) {
  try {
    await adminRequest(`/admin/catalog/skus/${sku.id}`, {
      method: "PATCH",
      body: { status: sku.status === "ACTIVE" ? "INACTIVE" : "ACTIVE" }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "更新服务套餐失败"
  }
}

onMounted(load)
</script>

<template>
  <div class="catalog">
    <div v-if="error" class="catalog-error">{{ error }}</div>

    <section class="catalog-panel">
      <div class="catalog-head">
        <div>
          <h2>游戏</h2>
          <p>控制用户首页可以看到并下单的游戏。</p>
        </div>
        <span>{{ games.length }} 个</span>
      </div>

      <div class="form-row game-form">
        <input v-model="gameCode" placeholder="内部标识，例如 apex" />
        <input v-model="gameName" placeholder="游戏名称" />
        <button @click="createGame">新增游戏</button>
      </div>

      <table>
        <thead>
          <tr><th>内部标识</th><th>名称</th><th>状态</th><th>排序</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="game in games" :key="game.id">
            <td><b>{{ game.code }}</b></td>
            <td>{{ game.name }}</td>
            <td><span class="chip">{{ game.status === "ACTIVE" ? "已启用" : "已停用" }}</span></td>
            <td>{{ game.sortOrder }}</td>
            <td>
              <button class="subtle" @click="toggleGame(game)">
                {{ game.status === "ACTIVE" ? "停用" : "启用" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="catalog-panel">
      <div class="catalog-head">
        <div>
          <h2>服务套餐</h2>
          <p>只配置用户真正需要选择的名称、时长和价格。</p>
        </div>
        <span>{{ skus.length }} 个</span>
      </div>

      <div class="form-row sku-form">
        <select v-model="skuGameId">
          <option v-for="game in games" :key="game.id" :value="game.id">
            {{ game.name }}
          </option>
        </select>
        <input v-model="skuName" placeholder="套餐名称，例如 娱乐陪玩 1 小时" />
        <input v-model.number="skuDuration" type="number" min="1" placeholder="时长 / 分钟" />
        <input v-model.number="skuPriceYuan" type="number" min="0" step="1" placeholder="价格 / 元" />
        <button @click="createSku">新增套餐</button>
      </div>

      <table>
        <thead>
          <tr><th>游戏</th><th>套餐</th><th>时长</th><th>价格</th><th>平台服务费</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="sku in skus" :key="sku.id">
            <td>{{ sku.gameName }}</td>
            <td><b>{{ sku.name }}</b></td>
            <td>{{ sku.durationMinutes }} 分钟</td>
            <td>¥{{ (sku.price / 100).toFixed(2) }}</td>
            <td>{{ (sku.platformFeeRate * 100).toFixed(0) }}%</td>
            <td><span class="chip">{{ sku.status === "ACTIVE" ? "已启用" : "已停用" }}</span></td>
            <td>
              <button class="subtle" @click="toggleSku(sku)">
                {{ sku.status === "ACTIVE" ? "停用" : "启用" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="loading" class="loading-row">正在同步配置…</div>
  </div>
</template>

<style scoped>
.catalog { display:grid; gap:20px; }
.catalog-panel { overflow:hidden; border:1px solid #ecebf1; border-radius:22px; background:white; }
.catalog-head { display:flex; align-items:center; justify-content:space-between; padding:22px 24px; border-bottom:1px solid #f0eff4; }
.catalog-head h2 { margin:0; font-size:17px; }
.catalog-head p { margin:6px 0 0; color:#92929d; font-size:12px; }
.catalog-head span { padding:7px 10px; border-radius:999px; background:#f1efff; color:#6c5ce7; font-size:11px; }
.form-row { display:grid; gap:10px; padding:18px 24px; background:#fafafe; }
.game-form { grid-template-columns:1fr 1.2fr auto; }
.sku-form { grid-template-columns:1.05fr 1.8fr .8fr .8fr auto; }
input,select { width:100%; border:1px solid #dedde6; border-radius:10px; padding:10px 11px; background:white; font:inherit; font-size:12px; }
.form-row button { border:0; border-radius:10px; padding:0 16px; background:#6c5ce7; color:white; cursor:pointer; font-size:12px; font-weight:700; }
table { width:100%; border-collapse:collapse; }
th,td { padding:13px 16px; border-top:1px solid #f1f0f5; text-align:left; font-size:12px; }
th { color:#92929d; font-size:10px; }
.chip { display:inline-block; padding:5px 8px; border-radius:999px; background:#f1efff; color:#6c5ce7; font-size:10px; font-weight:700; }
.subtle { border:1px solid #dedde6; border-radius:9px; padding:7px 10px; background:white; color:#686872; cursor:pointer; font-size:11px; }
.catalog-error { padding:12px 14px; border-radius:12px; background:#fff0f0; color:#c63d3d; font-size:12px; }
.loading-row { color:#92929d; text-align:center; font-size:12px; }
</style>
