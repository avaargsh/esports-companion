<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { adminRequest } from "../api"

type SkillStatus = "" | "PENDING" | "APPROVED" | "REJECTED" | "REVOKED"

type PlayerSkillLog = {
  id: string
  action: "APPROVE" | "REJECT" | "REVOKE" | string
  fromStatus: string
  fromStatusCode?: string
  toStatus: string
  toStatusCode?: string
  reason: string
  operatorUserId: string
  createdAt: string
}

type PlayerSkillReview = {
  id: string
  playerId: string
  playerName: string
  gameId: string
  gameName: string
  rank: string | null
  description: string
  evidenceUrl: string | null
  verificationStatus: string
  verificationStatusCode?: string
  reviewNote: string
  createdAt?: string
  updatedAt: string
  logs?: PlayerSkillLog[]
}

const statusTabs: Array<{ label: string; value: SkillStatus }> = [
  { label: "全部", value: "" },
  { label: "待审核", value: "PENDING" },
  { label: "已通过", value: "APPROVED" },
  { label: "已驳回", value: "REJECTED" },
  { label: "已撤销", value: "REVOKED" }
]

const statusText: Record<string, string> = {
  PENDING: "待审核",
  APPROVED: "已通过",
  REJECTED: "已驳回",
  REVOKED: "已撤销"
}

const actionText: Record<string, string> = {
  APPROVE: "审核通过",
  REJECT: "审核驳回",
  REVOKE: "撤销认证"
}

const loading = ref(false)
const error = ref("")
const status = ref<SkillStatus>("PENDING")
const rows = ref<PlayerSkillReview[]>([])
const detail = ref<PlayerSkillReview | null>(null)
const detailLoading = ref(false)
const revokeTarget = ref<PlayerSkillReview | null>(null)
const revokeReason = ref("")
const submitting = ref(false)

const pendingCount = computed(() => rows.value.filter((item) => (item.verificationStatusCode || item.verificationStatus) === "PENDING").length)
const approvedCount = computed(() => rows.value.filter((item) => (item.verificationStatusCode || item.verificationStatus) === "APPROVED").length)

function statusLabel(value: string) {
  return statusText[value] ?? value
}

function actionLabel(value: string) {
  return actionText[value] ?? value
}

function shortId(value: string) {
  return value.slice(0, 8)
}

function formatTime(value?: string) {
  if (!value) return "-"
  return new Date(value).toLocaleString()
}

async function load() {
  loading.value = true
  error.value = ""
  try {
    const query = status.value ? "?status=" + encodeURIComponent(status.value) : ""
    rows.value = await adminRequest<PlayerSkillReview[]>("/admin/player-skills" + query)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "技能认证列表加载失败"
  } finally {
    loading.value = false
  }
}

async function openDetail(row: PlayerSkillReview) {
  detail.value = row
  detailLoading.value = true
  error.value = ""
  try {
    detail.value = await adminRequest<PlayerSkillReview>("/admin/player-skills/" + row.id)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "技能认证详情加载失败"
  } finally {
    detailLoading.value = false
  }
}

async function approve(row: PlayerSkillReview) {
  submitting.value = true
  error.value = ""
  try {
    await adminRequest<PlayerSkillReview>("/admin/player-skills/" + row.id + "/approve", { method: "POST" })
    await load()
    if (detail.value?.id === row.id) await openDetail(row)
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : "审核通过失败"
  } finally {
    submitting.value = false
  }
}

async function reject(row: PlayerSkillReview) {
  const reason = window.prompt("请输入驳回原因", row.reviewNote || "证明材料不符合要求")?.trim()
  if (!reason) return
  submitting.value = true
  error.value = ""
  try {
    await adminRequest<PlayerSkillReview>("/admin/player-skills/" + row.id + "/reject", {
      method: "POST",
      body: { reason }
    })
    await load()
    if (detail.value?.id === row.id) await openDetail(row)
  } catch (reasonValue) {
    error.value = reasonValue instanceof Error ? reasonValue.message : "审核驳回失败"
  } finally {
    submitting.value = false
  }
}

function askRevoke(row: PlayerSkillReview) {
  revokeTarget.value = row
  revokeReason.value = ""
}

async function confirmRevoke() {
  if (!revokeTarget.value) return
  const reason = revokeReason.value.trim()
  if (!reason) {
    error.value = "请填写撤销原因"
    return
  }
  submitting.value = true
  error.value = ""
  try {
    await adminRequest<PlayerSkillReview>("/admin/player-skills/" + revokeTarget.value.id + "/revoke", {
      method: "POST",
      body: { reason }
    })
    const target = revokeTarget.value
    revokeTarget.value = null
    revokeReason.value = ""
    await load()
    if (detail.value?.id === target.id) await openDetail(target)
  } catch (reasonValue) {
    error.value = reasonValue instanceof Error ? reasonValue.message : "撤销认证失败"
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="skill-review">
    <div class="hero">
      <div>
        <p class="eyebrow">SKILL CERTIFICATION</p>
        <h2>技能认证审核</h2>
        <p>审核陪玩提交的游戏能力证明，图片来自 MinIO，所有操作会记录日志。</p>
      </div>
      <div class="metrics">
        <span><b>{{ pendingCount }}</b><small>待审核</small></span>
        <span><b>{{ approvedCount }}</b><small>已通过</small></span>
      </div>
    </div>

    <div class="toolbar">
      <div class="segmented">
        <button
          v-for="item in statusTabs"
          :key="item.value || 'all'"
          :class="{ active: status === item.value }"
          @click="status = item.value; load()"
        >
          {{ item.label }}
        </button>
      </div>
      <button class="ghost" @click="load">刷新</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>

    <div class="table-card">
      <div class="skill-row table-head">
        <span>陪玩</span>
        <span>游戏 / 段位</span>
        <span>证明图片</span>
        <span>状态</span>
        <span>更新时间</span>
        <span>操作</span>
      </div>

      <div v-if="loading" class="empty">加载中...</div>
      <div v-else-if="rows.length === 0" class="empty">暂无认证申请</div>

      <div v-for="row in rows" v-else :key="row.id" class="skill-row">
        <span class="identity">
          <b>{{ row.playerName }}</b>
          <small>{{ shortId(row.playerId) }}</small>
        </span>
        <span class="identity">
          <b>{{ row.gameName }}</b>
          <small>{{ row.rank || "未填写段位" }}</small>
        </span>
        <span>
          <button v-if="row.evidenceUrl" class="link-button" @click="openDetail(row)">查看图片</button>
          <small v-else>未上传</small>
        </span>
        <span><em class="status" :data-status="row.verificationStatus">{{ row.verificationStatus }}</em></span>
        <span>{{ formatTime(row.updatedAt) }}</span>
        <span class="actions">
          <button class="ghost" @click="openDetail(row)">详情</button>
          <button v-if="(row.verificationStatusCode || row.verificationStatus) === 'PENDING'" class="approve" :disabled="submitting" @click="approve(row)">通过</button>
          <button v-if="(row.verificationStatusCode || row.verificationStatus) === 'PENDING'" class="reject" :disabled="submitting" @click="reject(row)">驳回</button>
          <button v-if="(row.verificationStatusCode || row.verificationStatus) === 'APPROVED'" class="reject" :disabled="submitting" @click="askRevoke(row)">撤销</button>
        </span>
      </div>
    </div>
  </section>

  <div v-if="detail" class="modal-backdrop" @click.self="detail = null">
    <article class="detail-modal">
      <header>
        <div>
          <p class="eyebrow">CERTIFICATION DETAIL</p>
          <h3>{{ detail.playerName }} · {{ detail.gameName }}</h3>
        </div>
        <button class="ghost" @click="detail = null">关闭</button>
      </header>

      <div v-if="detailLoading" class="empty">详情加载中...</div>
      <template v-else>
        <div class="detail-grid">
          <div>
            <small>当前状态</small>
            <b>{{ detail.verificationStatus }}</b>
          </div>
          <div>
            <small>段位</small>
            <b>{{ detail.rank || "未填写" }}</b>
          </div>
          <div>
            <small>更新时间</small>
            <b>{{ formatTime(detail.updatedAt) }}</b>
          </div>
        </div>

        <div class="description">
          <small>申请说明</small>
          <p>{{ detail.description || "未填写说明" }}</p>
        </div>

        <div class="proof">
          <small>证明图片</small>
          <img v-if="detail.evidenceUrl" :src="detail.evidenceUrl" alt="技能认证证明图片" />
          <div v-else class="empty">未上传证明图片</div>
        </div>

        <div class="modal-actions">
          <button v-if="(detail.verificationStatusCode || detail.verificationStatus) === 'PENDING'" class="approve" :disabled="submitting" @click="approve(detail)">通过</button>
          <button v-if="(detail.verificationStatusCode || detail.verificationStatus) === 'PENDING'" class="reject" :disabled="submitting" @click="reject(detail)">驳回</button>
          <button v-if="(detail.verificationStatusCode || detail.verificationStatus) === 'APPROVED'" class="reject" :disabled="submitting" @click="askRevoke(detail)">撤销认证</button>
        </div>

        <div class="log-list">
          <h4>操作日志</h4>
          <div v-if="!detail.logs?.length" class="empty compact">暂无操作日志</div>
          <div v-for="log in detail.logs" v-else :key="log.id" class="log-item">
            <b>{{ actionLabel(log.action) }}</b>
            <span>{{ log.fromStatus }} → {{ log.toStatus }}</span>
            <p v-if="log.reason">{{ log.reason }}</p>
            <small>{{ formatTime(log.createdAt) }} · {{ shortId(log.operatorUserId) }}</small>
          </div>
        </div>
      </template>
    </article>
  </div>

  <div v-if="revokeTarget" class="modal-backdrop" @click.self="revokeTarget = null">
    <article class="confirm-modal">
      <header>
        <div>
          <p class="eyebrow">REVOKE CERTIFICATION</p>
          <h3>撤销已通过认证</h3>
        </div>
        <button class="ghost" @click="revokeTarget = null">关闭</button>
      </header>
      <p class="confirm-text">撤销后，该技能不会继续展示在用户端陪玩主页。</p>
      <label>
        撤销原因
        <textarea v-model="revokeReason" rows="4" placeholder="例如：复核发现证明图片与账号不一致"></textarea>
      </label>
      <div class="modal-actions">
        <button class="ghost" @click="revokeTarget = null">取消</button>
        <button class="reject" :disabled="submitting" @click="confirmRevoke">确认撤销</button>
      </div>
    </article>
  </div>
</template>

<style scoped>
.skill-review{display:grid;gap:22px}.hero{display:flex;justify-content:space-between;gap:24px;align-items:center;padding:28px;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:linear-gradient(135deg,#ffffff,#f3f4f6);color:#fff;box-shadow:0 10px 30px -5px rgba(0,0,0,.12)}.eyebrow{margin:0 0 10px;color:#111827;font-size:11px;font-weight:900;letter-spacing:4px}.hero h2,.detail-modal h3,.confirm-modal h3{margin:0}.hero p:not(.eyebrow){margin:10px 0 0;color:#6b7280}.metrics{display:flex;gap:12px}.metrics span{min-width:104px;padding:18px;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:rgba(0,0,0,.06)}.metrics b{display:block;color:#111827;font-size:28px}.metrics small{color:#6b7280}.toolbar{display:flex;justify-content:space-between;align-items:center;gap:16px}.segmented{display:inline-flex;padding:5px;border:1px solid rgba(0,0,0,.10);border-radius:14px;background:#0f0f10}.segmented button,.ghost,.approve,.reject,.link-button{border:0;border-radius:11px;padding:10px 14px;font-weight:800;cursor:pointer;white-space:nowrap}.segmented button{background:transparent;color:#6b7280}.segmented button.active{background:linear-gradient(135deg,#111827,#000000);color:#fff}.ghost{border:1px solid rgba(0,0,0,.10);background:#f3f4f6;color:#111827}.approve{background:rgba(0,0,0,.08);color:#111827}.reject{background:rgba(239,68,68,.14);color:#f87171}.link-button{background:rgba(0,0,0,.06);color:#111827}button:disabled{opacity:.55;cursor:wait}.error{margin:0;padding:12px 14px;border:1px solid rgba(239,68,68,.18);border-radius:12px;background:rgba(239,68,68,.1);color:#f87171;font-weight:800}.table-card{overflow:hidden;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:#ffffff;box-shadow:0 10px 30px -5px rgba(0,0,0,.12)}.skill-row{display:grid;grid-template-columns:1.15fr 1.2fr .8fr .75fr 1fr 1.25fr;align-items:center;gap:16px;padding:18px 24px;border-top:1px solid rgba(0,0,0,.06);color:#111827}.table-head{border-top:0;background:#f3f4f6;color:#374151;font-size:12px;font-weight:900}.identity{display:grid;gap:5px}.identity small{color:#6b7280}.status{display:inline-flex;padding:7px 10px;border-radius:999px;background:#f3f4f6;color:#6b7280;font-style:normal;font-size:12px;font-weight:900}.status[data-status="PENDING"]{background:rgba(0,0,0,.06);color:#111827}.status[data-status="APPROVED"]{background:rgba(0,0,0,.08);color:#111827}.status[data-status="REJECTED"]{background:rgba(239,68,68,.12);color:#f87171}.status[data-status="REVOKED"]{background:#f3f4f6;color:#374151}.actions,.modal-actions{display:flex;flex-wrap:wrap;gap:8px;align-items:center}.empty{padding:28px;text-align:center;color:#6b7280}.empty.compact{padding:14px}.modal-backdrop{position:fixed;inset:0;z-index:40;display:grid;place-items:center;padding:28px;background:rgba(0,0,0,.68)}.detail-modal,.confirm-modal{width:min(920px,100%);max-height:90vh;overflow:auto;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:#1d202a;box-shadow:0 28px 80px rgba(0,0,0,.45)}.confirm-modal{width:min(540px,100%)}.detail-modal header,.confirm-modal header{display:flex;justify-content:space-between;gap:16px;align-items:center;padding:24px 28px;border-bottom:1px solid rgba(0,0,0,.10)}.detail-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;padding:22px 28px}.detail-grid div,.description,.proof,.log-list,.confirm-modal label,.confirm-text{margin:0 28px 18px}.detail-grid div{padding:16px;border:1px solid rgba(0,0,0,.10);border-radius:14px;background:#ffffff}.detail-grid small,.description small,.proof small{display:block;margin-bottom:8px;color:#6b7280;font-weight:800}.description p,.confirm-text{color:#111827;line-height:1.7}.proof img{display:block;width:100%;max-height:360px;object-fit:contain;border:1px solid rgba(0,0,0,.10);border-radius:16px;background:#0f0f10}.modal-actions{padding:0 28px 22px}.log-list h4{margin:0 0 12px;color:#111827}.log-item{display:grid;gap:6px;padding:14px 0;border-top:1px solid rgba(0,0,0,.06)}.log-item span,.log-item small{color:#6b7280}.log-item p{margin:0;color:#111827}.confirm-modal label{display:grid;gap:10px;color:#111827;font-weight:900}.confirm-modal textarea{resize:vertical;min-height:108px;border:1px solid rgba(0,0,0,.10);border-radius:14px;padding:12px;background:#f3f4f6;color:#111827;font:inherit;outline:none}.confirm-modal textarea:focus{border-color:rgba(0,0,0,.20);box-shadow:0 0 0 3px rgba(0,0,0,.06)}@media(max-width:980px){.hero,.toolbar{align-items:stretch;flex-direction:column}.skill-row{grid-template-columns:1fr}.table-head{display:none}.detail-grid{grid-template-columns:1fr}}
</style>
