<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import CheckoutBar from "../../components/CheckoutBar.vue"
import EmptyState from "../../components/EmptyState.vue"
import type { Order, PublicOffering, PublicPlayer } from "../../types/domain"

const playerId=ref("")
const player=ref<PublicPlayer|null>(null)
const selectedOfferingId=ref("")
const remark=ref("")
const quantity=ref(1)
const loading=ref(true)
const failed=ref(false)
const creating=ref(false)

const selectedOffering=computed<PublicOffering|null>(()=>
  player.value?.offerings.find(i=>i.id===selectedOfferingId.value)??null
)
const totalAmount=computed(()=>(selectedOffering.value?.price||0)*quantity.value)
function changeQuantity(delta:number){quantity.value=Math.min(10,Math.max(1,quantity.value+delta))}

onLoad(async query=>{
  playerId.value=String(query?.id??"")
  if(!playerId.value){
    failed.value=true
    loading.value=false
    return
  }
  try{
    player.value=await request<PublicPlayer>(`/players/${playerId.value}`)
    selectedOfferingId.value=player.value.offerings[0]?.id??""
  }catch(error){
    failed.value=true
    uni.showToast({title:error instanceof Error?error.message:"大神资料加载失败",icon:"none"})
  }finally{loading.value=false}
})

async function createDesignatedOrder(){
  if(!selectedOffering.value||creating.value)return
  creating.value=true
  try{
    const identities=await getDemoIdentities()
    const order=await request<Order>("/orders",{
      method:"POST",
      userId:identities.customer.userId,
      data:{offering_id:selectedOffering.value.id,quantity:quantity.value,remark:remark.value.trim()}
    })
    uni.redirectTo({url:`/pages/order-detail/index?id=${order.id}`})
  }catch(error){
    uni.showToast({title:error instanceof Error?error.message:"下单失败",icon:"none"})
  }finally{creating.value=false}
}
</script>

<template>
  <view v-if="loading" class="safe-page">
    <view class="profile-skeleton skeleton"></view>
    <view v-for="n in 3" :key="n" class="row-skeleton skeleton"></view>
  </view>

  <view v-else-if="failed || !player" class="safe-page">
    <EmptyState
      title="大神资料暂时没加载出来"
      description="可以返回找大神列表后再试一次"
      symbol="↻"
    />
  </view>

  <view v-else class="page">
    <view class="profile-hero">
      <view class="glow"></view>
      <view class="profile-row">
        <view class="avatar-wrap">
          <image v-if="player.avatar_url" class="avatar-image" :src="player.avatar_url" mode="aspectFill" />
          <view v-else class="avatar">{{ player.display_name.slice(0,1) }}</view>
          <view v-if="player.service_status==='AVAILABLE'" class="presence"></view>
        </view>
        <view class="profile-main">
          <view class="name-row">
            <text class="name">{{ player.display_name }}</text>
            <text class="verified">已认证</text>
          </view>
          <text class="rating">
            {{ player.rating>0 ? player.rating.toFixed(1)+" ★" : "新大神" }}
            · {{ player.review_count }} 条评价
            · {{ player.order_count }} 单
          </text>
          <text class="availability">
            {{ player.service_status==="AVAILABLE" ? "现在可接单" : "当前暂离" }}
          </text>
        </view>
      </view>
      <text class="bio">{{ player.bio || "这个大神还没有填写自我介绍。" }}</text>
    </view>

    <view v-if="player.skills.length" class="section">
      <view class="section-head">
        <text class="section-title">认证技能</text>
        <text class="section-note">平台已审核</text>
      </view>
      <view class="skill-list">
        <view v-for="skill in player.skills" :key="skill.id" class="skill-badge">
          <text class="skill-game">{{ skill.game_name }}</text>
          <text class="skill-rank">{{ skill.rank }}</text>
        </view>
      </view>
    </view>

    <view class="direct-note">
      <view class="direct-icon">定</view>
      <view>
        <text class="direct-title">指定这位大神</text>
        <text class="direct-copy">支付后直接锁定，不进入公开抢单池。</text>
      </view>
    </view>

    <view class="section">
      <view class="section-head">
        <text class="section-title">选择服务</text>
        <text class="section-note">{{ player.offerings.length }} 个可选</text>
      </view>
      <view class="offering-list">
        <view
          v-for="offering in player.offerings"
          :key="offering.id"
          class="offering tap-scale"
          :class="{selected:selectedOfferingId===offering.id}"
          @click="selectedOfferingId=offering.id"
        >
          <view class="check"><text v-if="selectedOfferingId===offering.id">✓</text></view>
          <view class="offering-main">
            <text class="offering-name">{{ offering.game_name }} · {{ offering.sku_name }}</text>
            <text class="offering-desc">{{ offering.description || "由该大神直接服务" }}</text>
            <text class="offering-meta">{{ offering.duration_minutes }} 分钟</text>
          </view>
          <view class="price"><small>¥</small>{{ (offering.price/100).toFixed(0) }}</view>
        </view>
      </view>
    </view>

    <view class="section-card quantity-card">
      <view>
        <text class="card-label">服务数量</text>
        <text class="card-hint">可购买 1–10 份</text>
      </view>
      <view class="stepper">
        <button :disabled="quantity<=1" @click="changeQuantity(-1)">−</button>
        <text>{{ quantity }}</text>
        <button :disabled="quantity>=10" @click="changeQuantity(1)">＋</button>
      </view>
    </view>

    <view class="section-card">
      <view class="card-head">
        <text class="card-label">给大神留言</text>
        <text class="optional">选填</text>
      </view>
      <textarea v-model="remark" maxlength="500" placeholder="例如：娱乐局、开麦、想练辅助位…" />
    </view>

    <view class="section reviews-section">
      <view class="section-head">
        <text class="section-title">最近评价</text>
        <text class="section-note">{{ player.review_count }} 条</text>
      </view>
      <view v-if="!player.reviews.length" class="review-empty">暂无评价</view>
      <view v-for="review in player.reviews" :key="review.id" class="review">
        <view class="review-top">
          <text class="review-rating">{{ "★".repeat(review.rating) }}</text>
          <text class="review-score">{{ review.rating }}.0</text>
        </view>
        <text class="review-content">{{ review.content || "用户未填写文字评价" }}</text>
      </view>
    </view>

    <CheckoutBar
      :cents="totalAmount"
      :note="selectedOffering ? selectedOffering.game_name + ' · ' + selectedOffering.sku_name : ''"
      :primary-text="player.service_status==='AVAILABLE' ? '指定下单' : '大神暂不可接单'"
      :loading="creating"
      :disabled="!selectedOffering || player.service_status!=='AVAILABLE'"
      @primary="createDesignatedOrder"
    />
  </view>
</template>

<style scoped>
.page{padding:28rpx 28rpx 190rpx}
.profile-skeleton{height:280rpx;border-radius:38rpx}
.row-skeleton{height:140rpx;margin-top:18rpx;border-radius:28rpx}
.profile-hero{position:relative;overflow:hidden;padding:32rpx;border-radius:38rpx;background:linear-gradient(145deg,#1a1922,#28243a);color:#fff;box-shadow:0 24rpx 65rpx rgba(26,23,45,.18)}
.glow{position:absolute;width:260rpx;height:260rpx;right:-100rpx;top:-130rpx;border-radius:50%;background:rgba(111,91,232,.28)}
.profile-row{position:relative;display:flex;gap:22rpx;align-items:center}
.avatar-wrap{position:relative;flex:none}
.avatar,.avatar-image{width:116rpx;height:116rpx;border-radius:34rpx}
.avatar{display:flex;align-items:center;justify-content:center;background:linear-gradient(145deg,#6757e6,#8b79f5);font-size:39rpx;font-weight:850}
.presence{position:absolute;right:-2rpx;bottom:-2rpx;width:24rpx;height:24rpx;border:5rpx solid #22202e;border-radius:50%;background:#38cc84}
.profile-main{flex:1;min-width:0}
.name-row{display:flex;align-items:center;gap:10rpx}
.name{overflow:hidden;font-size:33rpx;font-weight:850;text-overflow:ellipsis;white-space:nowrap}
.verified{flex:none;padding:5rpx 9rpx;border-radius:999rpx;background:rgba(139,121,245,.15);color:#bcb0ff;font-size:15rpx;font-weight:750}
.rating{display:block;margin-top:9rpx;color:#b4b2bf;font-size:19rpx}
.availability{display:inline-block;margin-top:10rpx;padding:6rpx 10rpx;border-radius:999rpx;background:rgba(52,199,124,.11);color:#62d99a;font-size:17rpx}
.bio{position:relative;display:block;margin-top:23rpx;padding-top:20rpx;border-top:1rpx solid rgba(255,255,255,.07);color:#a6a4b2;font-size:20rpx;line-height:1.62}
.section{margin-top:34rpx}
.section-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:17rpx}
.section-title{font-size:29rpx;font-weight:820}
.section-note{color:var(--muted);font-size:18rpx}
.skill-list{display:flex;flex-wrap:wrap;gap:9rpx}
.skill-badge{display:flex;gap:8rpx;align-items:center;padding:11rpx 14rpx;border:1rpx solid #e7e6ee;border-radius:18rpx;background:#fff}
.skill-game{font-size:19rpx;font-weight:750}
.skill-rank{color:var(--brand);font-size:18rpx}
.direct-note{display:flex;gap:16rpx;align-items:center;margin-top:24rpx;padding:20rpx 22rpx;border-radius:24rpx;background:var(--brand-soft)}
.direct-icon{width:50rpx;height:50rpx;display:flex;align-items:center;justify-content:center;border-radius:16rpx;background:#fff;color:var(--brand);font-size:18rpx;font-weight:850}
.direct-title,.direct-copy{display:block}.direct-title{color:#5c4bd0;font-size:21rpx;font-weight:780}.direct-copy{margin-top:4rpx;color:#766ab4;font-size:17rpx}
.offering-list{display:flex;flex-direction:column;gap:12rpx}
.offering{display:flex;gap:17rpx;align-items:center;padding:24rpx;border:2rpx solid transparent;border-radius:29rpx;background:#fff;box-shadow:var(--shadow-card)}
.offering.selected{border-color:var(--brand);background:var(--brand-ghost)}
.check{width:37rpx;height:37rpx;display:flex;align-items:center;justify-content:center;border:2rpx solid #d7d6df;border-radius:50%;color:#fff;font-size:17rpx}
.selected .check{border-color:var(--brand);background:var(--brand)}
.offering-main{flex:1;min-width:0}
.offering-name{display:block;font-size:24rpx;font-weight:780}.offering-desc,.offering-meta{display:block;margin-top:6rpx;color:var(--muted);font-size:18rpx}
.price{flex:none;font-size:32rpx;font-weight:850}.price small,.footer-price small{font-size:17rpx;font-weight:700}
.section-card{margin-top:18rpx;padding:26rpx 28rpx;border-radius:29rpx;background:#fff;box-shadow:var(--shadow-card)}
.quantity-card{display:flex;align-items:center;justify-content:space-between;gap:20rpx}
.card-label{display:block;font-size:24rpx;font-weight:760}.card-hint{display:block;margin-top:5rpx;color:var(--muted);font-size:18rpx}
.card-head{display:flex;align-items:center;gap:9rpx}.optional{color:var(--muted);font-size:17rpx}
.stepper{display:flex;align-items:center;gap:18rpx}.stepper button{width:58rpx;height:58rpx;margin:0;padding:0;line-height:58rpx;border-radius:18rpx;background:var(--brand-soft);color:var(--brand);font-size:28rpx}.stepper button[disabled]{opacity:.35}.stepper text{min-width:34rpx;text-align:center;font-size:27rpx;font-weight:800}
textarea{width:100%;height:130rpx;margin-top:15rpx;padding:18rpx;border-radius:20rpx;background:#f7f7fa;font-size:21rpx}
.reviews-section{padding-bottom:4rpx}.review{margin-bottom:12rpx;padding:23rpx;border-radius:26rpx;background:#fff}.review-top{display:flex;align-items:center;justify-content:space-between}.review-rating{color:#e9aa2d;font-size:21rpx;letter-spacing:2rpx}.review-score{color:var(--muted);font-size:17rpx}.review-content{display:block;margin-top:10rpx;color:var(--ink-2);font-size:20rpx;line-height:1.55}.review-empty{padding:40rpx;border-radius:26rpx;background:#fff;color:var(--muted);text-align:center;font-size:20rpx}
</style>
