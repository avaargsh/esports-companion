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
const skuServiceType = ref("ENTERTAINMENT")
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
    error.value = reason instanceof Error ? reason.message : "CATALOG_LOAD_FAILED"
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
    error.value = reason instanceof Error ? reason.message : "CREATE_GAME_FAILED"
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
    error.value = reason instanceof Error ? reason.message : "UPDATE_GAME_FAILED"
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
        service_type: skuServiceType.value.trim() || "ENTERTAINMENT",
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
    error.value = reason instanceof Error ? reason.message : "CREATE_SKU_FAILED"
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
    error.value = reason instanceof Error ? reason.message : "UPDATE_SKU_FAILED"
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
          <h2>Game Catalog</h2>
          <p>控制用户端可见的游戏与下单入口。</p>
        </div>
        <span>{{ games.length }} games</span>
      </div>

      <div class="form-row">
        <input v-model="gameCode" placeholder="code，例如 apex" />
        <input v-model="gameName" placeholder="游戏名称" />
        <button @click="createGame">新增 Game</button>
      </div>

      <table>
        <thead>
          <tr><th>Code</th><th>名称</th><th>状态</th><th>排序</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="game in games" :key="game.id">
            <td><b>{{ game.code }}</b></td>
            <td>{{ game.name }}</td>
            <td><span class="chip">{{ game.status }}</span></td>
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
          <h2>Service SKU</h2>
          <p>价格在下单时快照进 Order；后续改价不影响历史订单。</p>
        </div>
        <span>{{ skus.length }} skus</span>
      </div>

      <div class="form-row sku-form">
        <select v-model="skuGameId">
          <option v-for="game in games" :key="game.id" :value="game.id">
            {{ game.name }}
          </option>
        </select>
        <input v-model="skuName" placeholder="套餐名称" />
        <input v-model="skuServiceType" placeholder="service_type" />
        <input v-model.number="skuDuration" type="number" min="1" placeholder="分钟" />
        <input v-model.number="skuPriceYuan" type="number" min="0" step="1" placeholder="价格/元" />
        <button @click="createSku">新增 SKU</button>
      </div>

      <table>
        <thead>
          <tr><th>游戏</th><th>SKU</th><th>类型</th><th>时长</th><th>价格</th><th>平台费</th><th>状态</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="sku in skus" :key="sku.id">
            <td>{{ sku.gameName }}</td>
            <td><b>{{ sku.name }}</b></td>
            <td>{{ sku.serviceType }}</td>
            <td>{{ sku.durationMinutes }} min</td>
            <td>¥{{ (sku.price / 100).toFixed(2) }}</td>
            <td>{{ (sku.platformFeeRate * 100).toFixed(0) }}%</td>
            <td><span class="chip">{{ sku.status }}</span></td>
            <td>
              <button class="subtle" @click="toggleSku(sku)">
                {{ sku.status === "ACTIVE" ? "停用" : "启用" }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="loading" class="loading-row">同步 Catalog...</div>
  </div>
</template>

<style scoped>
.catalog { display: grid; gap: 20px; }
.catalog-panel { overflow: hidden; border: 1px solid #ecebf1; border-radius: 22px; background: white; }
.catalog-head { display: flex; align-items: center; justify-content: space-between; padding: 22px 24px; border-bottom: 1px solid #f0eff4; }
.catalog-head h2 { margin: 0; font-size: 17px; }
.catalog-head p { margin: 6px 0 0; color: #92929d; font-size: 12px; }
.catalog-head span { padding: 7px 10px; border-radius: 999px; background: #f1efff; color: #6c5ce7; font-size: 11px; }
.form-row { display: grid; grid-template-columns: 1fr 1.2fr auto; gap: 10px; padding: 18px 24px; background: #fafafe; }
.form-row.sku-form { grid-template-columns: 1.1fr 1.5fr 1.1fr .7fr .7fr auto; }
input, select { width: 100%; border: 1px solid #dedde6; border-radius: 10px; padding: 10px 11px; background: white; font: inherit; font-size: 12px; }
.form-row button { border: 0; border-radius: 10px; padding: 0 16px; background: #6c5ce7; color: white; cursor: pointer; font-size: 12px; font-weight: 700; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 13px 16px; border-top: 1px solid #f1f0f5; text-align: left; font-size: 12px; }
th { color: #92929d; font-size: 10px; }
.chip { display: inline-block; padding: 5px 8px; border-radius: 999px; background: #f1efff; color: #6c5ce7; font-size: 10px; font-weight: 700; }
.subtle { border: 1px solid #dedde6; border-radius: 9px; padding: 7px 10px; background: white; color: #686872; cursor: pointer; font-size: 11px; }
.catalog-error { padding: 12px 14px; border-radius: 12px; background: #fff0f0; color: #c63d3d; font-size: 12px; }
.loading-row { color: #92929d; text-align: center; font-size: 12px; }
</style>
