<script setup lang="ts">
import { computed, onMounted, ref } from "vue"

import { adminRequest } from "../api"

type CatalogGame = {
  id: string
  code: string
  name: string
  iconUrl?: string | null
  status: string
  statusCode?: string
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
  statusCode?: string
}

type CatalogImageUpload = {
  key: string
  url: string
}

const games = ref<CatalogGame[]>([])
const skus = ref<CatalogSku[]>([])
const loading = ref(false)
const error = ref("")
const brokenIcons = ref<Record<string, boolean>>({})
const uploading = ref(false)

const gameCode = ref("")
const gameName = ref("")
const gameIconUrl = ref("")
const skuGameId = ref("")
const skuName = ref("")
const skuDuration = ref(60)
const skuPriceYuan = ref(30)

const editingGameId = ref("")
const editGameName = ref("")
const editGameIconUrl = ref("")
const editGameSortOrder = ref(0)

const activeGames = computed(() => games.value.filter((item) => (item.statusCode || item.status) === "ACTIVE").length)
const activeSkus = computed(() => skus.value.filter((item) => (item.statusCode || item.status) === "ACTIVE").length)

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || "")
      resolve(result.includes(",") ? result.split(",")[1] : result)
    }
    reader.onerror = () => reject(new Error("IMAGE_READ_FAILED"))
    reader.readAsDataURL(file)
  })
}

async function uploadImage(file: File): Promise<string> {
  const dataBase64 = await readFileAsBase64(file)
  const result = await adminRequest<CatalogImageUpload>("/admin/catalog/images", {
    method: "POST",
    body: {
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      data_base64: dataBase64
    }
  })
  return result.url
}

async function handleCreateImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file) return
  uploading.value = true
  error.value = ""
  try {
    gameIconUrl.value = await uploadImage(file)
  } catch (reason) {
    const message = reason instanceof Error ? reason.message : "图片上传失败"
    error.value = message === "UNSUPPORTED_IMAGE_TYPE"
      ? "仅支持 jpg、png、gif、webp、bmp、svg 图片"
      : message === "IMAGE_TOO_LARGE"
        ? "图片不能超过 5MB"
        : message
  } finally {
    uploading.value = false
  }
}

async function handleEditImage(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ""
  if (!file) return
  uploading.value = true
  error.value = ""
  try {
    editGameIconUrl.value = await uploadImage(file)
  } catch (reason) {
    const message = reason instanceof Error ? reason.message : "图片上传失败"
    error.value = message === "UNSUPPORTED_IMAGE_TYPE"
      ? "仅支持 jpg、png、gif、webp、bmp、svg 图片"
      : message === "IMAGE_TOO_LARGE"
        ? "图片不能超过 5MB"
        : message
  } finally {
    uploading.value = false
  }
}

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
  const code = gameCode.value.trim()
  const name = gameName.value.trim()
  const iconUrl = gameIconUrl.value.trim()
  if (!code || !name) return
  try {
    await adminRequest("/admin/catalog/games", {
      method: "POST",
      body: {
        code,
        name,
        icon_url: iconUrl || null,
        sort_order: games.value.length * 10 + 10
      }
    })
    gameCode.value = ""
    gameName.value = ""
    gameIconUrl.value = ""
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "新增游戏失败"
  }
}

function startEditGame(game: CatalogGame) {
  editingGameId.value = game.id
  editGameName.value = game.name
  editGameIconUrl.value = game.iconUrl || ""
  editGameSortOrder.value = game.sortOrder
}

function cancelEditGame() {
  editingGameId.value = ""
  editGameName.value = ""
  editGameIconUrl.value = ""
  editGameSortOrder.value = 0
}

async function saveGame(game: CatalogGame) {
  const name = editGameName.value.trim()
  if (!name) return
  try {
    await adminRequest(`/admin/catalog/games/${game.id}`, {
      method: "PATCH",
      body: {
        name,
        icon_url: editGameIconUrl.value.trim() || null,
        sort_order: Number(editGameSortOrder.value)
      }
    })
    cancelEditGame()
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "保存游戏失败"
  }
}

async function toggleGame(game: CatalogGame) {
  try {
    await adminRequest(`/admin/catalog/games/${game.id}`, {
      method: "PATCH",
      body: { status: (game.statusCode || game.status) === "ACTIVE" ? "INACTIVE" : "ACTIVE" }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "更新游戏失败"
  }
}

async function deleteGame(game: CatalogGame) {
  const confirmed = window.confirm(`确认删除「${game.name}」？历史订单会保留，游戏和套餐会从配置列表隐藏。`)
  if (!confirmed) return
  try {
    await adminRequest(`/admin/catalog/games/${game.id}`, { method: "DELETE" })
    if (editingGameId.value === game.id) cancelEditGame()
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "删除游戏失败"
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
      body: { status: (sku.statusCode || sku.status) === "ACTIVE" ? "INACTIVE" : "ACTIVE" }
    })
    await load()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "更新服务套餐失败"
  }
}

function markIconBroken(gameId: string) {
  brokenIcons.value = { ...brokenIcons.value, [gameId]: true }
}

onMounted(load)
</script>

<template>
  <div class="catalog">
    <div v-if="error" class="catalog-error">{{ error }}</div>

    <section class="hero-panel">
      <div>
        <p>CATALOG CONFIG</p>
        <h2>游戏与服务配置</h2>
        <span>游戏图片上传到 MinIO，数据库保存可外网访问的图片 URL。</span>
      </div>
      <div class="hero-stats">
        <article><strong>{{ activeGames }}</strong><span>启用游戏</span></article>
        <article><strong>{{ activeSkus }}</strong><span>启用套餐</span></article>
      </div>
    </section>

    <section class="catalog-panel">
      <div class="catalog-head">
        <div>
          <h2>游戏配置</h2>
          <p>新增或编辑游戏时直接上传图片，保存时数据库写入 MinIO 访问 URL。</p>
        </div>
        <span>{{ games.length }} 个</span>
      </div>

      <div class="game-create">
        <label>
          <span>内部标识</span>
          <input v-model="gameCode" placeholder="例如 valorant" />
        </label>
        <label>
          <span>游戏名称</span>
          <input v-model="gameName" placeholder="例如 无畏契约" />
        </label>
        <div class="image-picker wide">
          <div class="preview-box">
            <img v-if="gameIconUrl" :src="gameIconUrl" alt="游戏图标预览" />
            <span v-else>图</span>
          </div>
          <div class="picker-copy">
            <strong>游戏图片</strong>
            <small>{{ gameIconUrl ? "已上传，保存后写入数据库" : "上传 PNG / JPG / SVG 到 MinIO" }}</small>
          </div>
          <label class="upload-control">
            <input type="file" accept="image/*" :disabled="uploading" @change="handleCreateImage" />
            <span>{{ uploading ? "上传中" : "上传图片" }}</span>
          </label>
        </div>
        <button type="button" @click="createGame">新增游戏</button>
      </div>

      <div class="game-table">
        <div class="game-row head"><span>游戏</span><span>图片</span><span>状态</span><span>排序</span><span>操作</span></div>
        <div v-for="game in games" :key="game.id" class="game-row" :class="{ editing: editingGameId === game.id }">
          <template v-if="editingGameId === game.id">
            <span class="edit-cell">
              <input v-model="editGameName" placeholder="游戏名称" />
              <small>{{ game.code }}</small>
            </span>
            <span class="edit-image-cell">
              <span class="preview-box small">
                <img v-if="editGameIconUrl" :src="editGameIconUrl" alt="游戏图标预览" />
                <span v-else>图</span>
              </span>
              <span class="picker-copy compact">
                <strong>{{ editGameIconUrl ? "图片已上传" : "未上传图片" }}</strong>
                <small>保存后写入数据库</small>
              </span>
              <label class="inline-upload">
                <input type="file" accept="image/*" :disabled="uploading" @change="handleEditImage" />
                <span>{{ uploading ? "上传中" : "更换图片" }}</span>
              </label>
            </span>
            <span><em :class="['chip', game.status === 'ACTIVE' ? 'active' : 'muted']">{{ (game.statusCode || game.status) === "ACTIVE" ? "已启用" : "已停用" }}</em></span>
            <span><input v-model.number="editGameSortOrder" class="sort-input" type="number" /></span>
            <span class="row-actions">
              <button class="primary-small" type="button" @click="saveGame(game)">保存</button>
              <button class="subtle" type="button" @click="cancelEditGame">取消</button>
            </span>
          </template>
          <template v-else>
            <span class="game-cell">
              <span class="game-icon">
                <img v-if="game.iconUrl && !brokenIcons[game.id]" :src="game.iconUrl" :alt="game.name" @error="markIconBroken(game.id)" />
                <b v-else>{{ game.name.slice(0, 1) }}</b>
              </span>
              <span><b>{{ game.name }}</b><small>{{ game.code }}</small></span>
            </span>
            <span class="url-cell">{{ game.iconUrl ? "已上传" : "未上传" }}</span>
            <span><em :class="['chip', game.status === 'ACTIVE' ? 'active' : 'muted']">{{ (game.statusCode || game.status) === "ACTIVE" ? "已启用" : "已停用" }}</em></span>
            <span>{{ game.sortOrder }}</span>
            <span class="row-actions">
              <button class="subtle" type="button" @click="startEditGame(game)">编辑</button>
              <button class="subtle" type="button" @click="toggleGame(game)">{{ (game.statusCode || game.status) === "ACTIVE" ? "停用" : "启用" }}</button>
              <button class="danger" type="button" @click="deleteGame(game)">删除</button>
            </span>
          </template>
        </div>
      </div>
    </section>

    <section class="catalog-panel">
      <div class="catalog-head">
        <div>
          <h2>服务套餐</h2>
          <p>配置用户下单时真正会选择的套餐、时长和价格。</p>
        </div>
        <span>{{ skus.length }} 个</span>
      </div>

      <div class="sku-create">
        <select v-model="skuGameId">
          <option v-for="game in games" :key="game.id" :value="game.id">{{ game.name }}</option>
        </select>
        <input v-model="skuName" placeholder="套餐名称，例如 娱乐陪玩 1 小时" />
        <input v-model.number="skuDuration" type="number" min="1" placeholder="时长 / 分钟" />
        <input v-model.number="skuPriceYuan" type="number" min="0" step="1" placeholder="价格 / 元" />
        <button type="button" @click="createSku">新增套餐</button>
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
            <td><em :class="['chip', sku.status === 'ACTIVE' ? 'active' : 'muted']">{{ (sku.statusCode || sku.status) === "ACTIVE" ? "已启用" : "已停用" }}</em></td>
            <td><button class="subtle" type="button" @click="toggleSku(sku)">{{ (sku.statusCode || sku.status) === "ACTIVE" ? "停用" : "启用" }}</button></td>
          </tr>
        </tbody>
      </table>
    </section>

    <div v-if="loading" class="loading-row">正在同步配置...</div>
  </div>
</template>

<style scoped>
.catalog{display:grid;gap:20px}.hero-panel{display:flex;align-items:center;justify-content:space-between;gap:24px;padding:26px 28px;border-radius:22px;background:#17171f;color:#fff;box-shadow:0 18px 55px rgba(22,18,40,.12)}.hero-panel p{margin:0 0 8px;color:#9b8cff;font-size:11px;font-weight:800;letter-spacing:2px}.hero-panel h2{margin:0;font-size:25px}.hero-panel span{display:block;margin-top:8px;color:#a7a5b2;font-size:12px}.hero-stats{display:flex;gap:12px}.hero-stats article{min-width:118px;padding:16px;border:1px solid rgba(255,255,255,.08);border-radius:16px;background:rgba(255,255,255,.05)}.hero-stats strong,.hero-stats span{display:block}.hero-stats strong{font-size:26px}.hero-stats span{margin-top:4px;font-size:11px}.catalog-panel{overflow:hidden;border:1px solid #ecebf1;border-radius:22px;background:#fff;box-shadow:0 16px 45px rgba(30,23,70,.035)}.catalog-head{display:flex;align-items:center;justify-content:space-between;padding:22px 24px;border-bottom:1px solid #f0eff4}.catalog-head h2{margin:0;font-size:17px}.catalog-head p{margin:6px 0 0;color:#92929d;font-size:12px}.catalog-head>span{padding:7px 10px;border-radius:999px;background:#f1efff;color:#6c5ce7;font-size:11px}.game-create,.sku-create{display:grid;gap:12px;padding:18px 24px;background:#fbfbfe}.game-create{grid-template-columns:1fr 1fr 2fr auto}.sku-create{grid-template-columns:1.05fr 1.8fr .8fr .8fr auto}label span{display:block;margin-bottom:7px;color:#777783;font-size:11px;font-weight:700}input,select{width:100%;height:39px;border:1px solid #dedde6;border-radius:11px;padding:0 12px;background:#fff;color:#24242d;font:inherit;font-size:12px}button{white-space:nowrap}.game-create button,.sku-create button{align-self:end;height:39px;border:0;border-radius:11px;padding:0 16px;background:#6c5ce7;color:#fff;cursor:pointer;font-size:12px;font-weight:800}.image-picker{display:flex;align-items:center;gap:12px;min-height:58px;padding:9px 10px;border:1px solid #dedde6;border-radius:14px;background:#fff}.preview-box{width:42px;height:42px;display:grid;place-items:center;flex:none;border-radius:13px;background:#f1efff;overflow:hidden;color:#6c5ce7;font-size:13px;font-weight:800}.preview-box.small{width:38px;height:38px}.preview-box img{width:100%;height:100%;object-fit:cover}.picker-copy{flex:1;min-width:0}.picker-copy strong,.picker-copy small{display:block}.picker-copy strong{font-size:12px}.picker-copy small{margin-top:4px;color:#92929d;font-size:10px}.picker-copy.compact strong{font-size:11px}.upload-control,.inline-upload{position:relative;display:flex;align-items:center;justify-content:center;border:1px solid #dedde6;border-radius:11px;background:#fff;color:#6c5ce7;cursor:pointer;font-size:12px;font-weight:800}.upload-control{align-self:end;height:39px;padding:0 14px}.upload-control input,.inline-upload input{position:absolute;inset:0;opacity:0;cursor:pointer}.inline-upload{height:32px;padding:0 10px}.game-table{padding:0 10px 12px}.game-row{display:grid;grid-template-columns:1.2fr 1.55fr .55fr .38fr 1fr;gap:14px;align-items:center;min-height:72px;padding:12px 14px;border-top:1px solid #f1f0f5;font-size:12px}.game-row.head{min-height:40px;color:#92929d;font-size:10px;font-weight:800}.game-row.editing{background:#fbfbff}.game-cell{display:flex;align-items:center;gap:12px;min-width:0}.game-cell b,.game-cell small,.edit-cell small{display:block}.game-cell small,.edit-cell small{margin-top:4px;color:#9f9ea8;font-size:10px}.game-icon{width:40px;height:40px;display:grid;place-items:center;flex:none;border-radius:13px;background:#f1efff;overflow:hidden}.game-icon img{width:100%;height:100%;object-fit:cover}.game-icon b{color:#6c5ce7;font-size:15px}.url-cell{overflow:hidden;color:#8f8e99;text-overflow:ellipsis;white-space:nowrap}.edit-cell{display:grid;gap:7px}.edit-image-cell{display:flex;align-items:center;gap:10px;min-width:0}.sort-input{max-width:90px}.chip{display:inline-block;padding:5px 8px;border-radius:999px;font-style:normal;font-size:10px;font-weight:800}.chip.active{background:#eafbf2;color:#198754}.chip.muted{background:#f0eff4;color:#777783}.row-actions{display:flex;flex-wrap:wrap;gap:7px}.subtle,.danger,.primary-small{border:1px solid #dedde6;border-radius:9px;padding:7px 10px;background:#fff;color:#686872;cursor:pointer;font-size:11px}.primary-small{border-color:#6c5ce7;background:#6c5ce7;color:#fff}.danger{border-color:#ffe0e0;background:#fff5f5;color:#c63d3d}table{width:100%;border-collapse:collapse}th,td{padding:13px 16px;border-top:1px solid #f1f0f5;text-align:left;font-size:12px}th{color:#92929d;font-size:10px}.catalog-error{padding:12px 14px;border-radius:12px;background:#fff0f0;color:#c63d3d;font-size:12px}.loading-row{color:#92929d;text-align:center;font-size:12px}@media(max-width:1250px){.game-create,.sku-create{grid-template-columns:1fr 1fr}.game-create .wide{grid-column:1/-1}.game-row{grid-template-columns:1.2fr 1.4fr .6fr .4fr .8fr}}
</style>
