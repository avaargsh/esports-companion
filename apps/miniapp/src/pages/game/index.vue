<script setup lang="ts">
import { computed, ref } from "vue"
import { onLoad } from "@dcloudio/uni-app"
import { request } from "../../api/client"
import { getDemoIdentities } from "../../api/demo"
import type { Order, ServiceSku } from "../../types/domain"

const gameId=ref("")
const gameName=ref("选择服务")
const skus=ref<ServiceSku[]>([])
const selectedId=ref("")
const remark=ref("")
const quantity=ref(1)
const creating=ref(false)

const selected=computed(()=>skus.value.find(i=>i.id===selectedId.value)??null)
const totalAmount=computed(()=>(selected.value?.price||0)*quantity.value)
function changeQuantity(delta:number){ quantity.value=Math.min(10,Math.max(1,quantity.value+delta)) }

onLoad(async query=>{
  gameId.value=String(query?.id??"")
  gameName.value=decodeURIComponent(String(query?.name??"选择服务"))
  if(!gameId.value)return
  skus.value=await request<ServiceSku[]>(`/games/${gameId.value}/skus`)
  selectedId.value=skus.value[0]?.id??""
})

async function createOrder(){
  if(!selected.value||creating.value)return
  creating.value=true
  try{
    const identities=await getDemoIdentities()
    const order=await request<Order>("/orders",{
      method:"POST",
      userId:identities.customer.userId,
      data:{sku_id:selected.value.id,quantity:quantity.value,remark:remark.value.trim()}
    })
    uni.redirectTo({url:`/pages/order-detail/index?id=${order.id}`})
  }catch(error){
    uni.showToast({title:error instanceof Error?error.message:"下单失败",icon:"none"})
  }finally{creating.value=false}
}
</script>

<template>
  <view class="safe-page game-page">
    <view class="heading">
      <text class="eyebrow">QUICK MATCH</text>
      <text class="title">{{ gameName }}</text>
      <text class="subtitle">选一个服务，支付后进入平台匹配。</text>
    </view>

    <view class="service-title">
      <text>选择服务</text>
      <text class="count">{{ skus.length }} 个套餐</text>
    </view>

    <view class="sku-list">
      <view
        v-for="sku in skus"
        :key="sku.id"
        class="sku-card tap-scale"
        :class="{selected:selectedId===sku.id}"
        @click="selectedId=sku.id"
      >
        <view class="radio"><text v-if="selectedId===sku.id">✓</text></view>
        <view class="sku-main">
          <text class="sku-name">{{ sku.name }}</text>
          <text class="meta">{{ sku.duration_minutes }} 分钟 · 平台匹配</text>
        </view>
        <view class="price"><small>¥</small>{{ (sku.price/100).toFixed(0) }}</view>
      </view>
    </view>

    <view class="option-card">
      <view>
        <text class="option-label">服务数量</text>
        <text class="option-hint">最多 10 份</text>
      </view>
      <view class="stepper">
        <button :disabled="quantity<=1" @click="changeQuantity(-1)">−</button>
        <text>{{ quantity }}</text>
        <button :disabled="quantity>=10" @click="changeQuantity(1)">＋</button>
      </view>
    </view>

    <view class="remark-card">
      <view class="remark-head">
        <text class="option-label">给陪玩留言</text>
        <text class="optional">选填</text>
      </view>
      <textarea
        v-model="remark"
        maxlength="500"
        placeholder="例如：娱乐局、开麦、想练辅助位…"
      />
    </view>

    <view class="promise">
      <text>平台担保交易</text><text>·</text><text>服务完成后结算</text><text>·</text><text>支持订单售后</text>
    </view>

    <view class="footer">
      <view>
        <text class="pay-label">合计</text>
        <text v-if="selected" class="total"><small>¥</small>{{ (totalAmount/100).toFixed(2) }}</text>
      </view>
      <button class="buy" :disabled="!selected" :loading="creating" @click="createOrder">
        确认下单
      </button>
    </view>
  </view>
</template>

<style scoped>
.game-page { padding-bottom:180rpx; }
.heading { padding:18rpx 3rpx 30rpx; }
.eyebrow { display:block;color:var(--brand);font-size:16rpx;font-weight:800;letter-spacing:2rpx; }
.title { display:block;margin-top:10rpx;font-size:40rpx;font-weight:850;letter-spacing:-1rpx; }
.subtitle { display:block;margin-top:9rpx;color:var(--muted);font-size:20rpx; }
.service-title { display:flex;align-items:center;justify-content:space-between;margin-bottom:15rpx;font-size:24rpx;font-weight:780; }
.count { color:var(--muted);font-size:18rpx;font-weight:500; }
.sku-list { display:flex;flex-direction:column;gap:12rpx; }
.sku-card {
  display:flex;align-items:center;gap:18rpx;padding:25rpx;border:2rpx solid transparent;
  border-radius:30rpx;background:#fff;box-shadow:var(--shadow-card);
}
.sku-card.selected { border-color:var(--brand); background:var(--brand-ghost); }
.radio {
  width:38rpx;height:38rpx;display:flex;align-items:center;justify-content:center;
  border:2rpx solid #d6d5dd;border-radius:50%;color:#fff;font-size:18rpx;
}
.selected .radio { border-color:var(--brand);background:var(--brand); }
.sku-main { flex:1;min-width:0; }
.sku-name { display:block;font-size:25rpx;font-weight:780; }
.meta { display:block;margin-top:7rpx;color:var(--muted);font-size:19rpx; }
.price { color:var(--ink);font-size:34rpx;font-weight:850; }
.price small,.total small { font-size:18rpx;font-weight:700; }
.option-card,.remark-card {
  margin-top:18rpx;padding:26rpx 28rpx;border-radius:30rpx;background:#fff;box-shadow:var(--shadow-card);
}
.option-card { display:flex;align-items:center;justify-content:space-between;gap:20rpx; }
.option-label { display:block;font-size:24rpx;font-weight:760; }
.option-hint,.optional { color:var(--muted);font-size:18rpx; }
.option-hint { display:block;margin-top:5rpx; }
.stepper { display:flex;align-items:center;gap:18rpx; }
.stepper button {
  width:58rpx;height:58rpx;margin:0;padding:0;line-height:58rpx;border-radius:18rpx;
  background:#f1efff;color:var(--brand);font-size:28rpx;
}
.stepper button[disabled]{opacity:.35}
.stepper text{min-width:34rpx;text-align:center;font-size:27rpx;font-weight:800}
.remark-head { display:flex;align-items:center;gap:10rpx; }
textarea {
  width:100%;height:130rpx;margin-top:16rpx;padding:18rpx;border-radius:20rpx;background:#f7f7fa;font-size:21rpx;
}
.promise { display:flex;justify-content:center;gap:9rpx;margin-top:22rpx;color:var(--muted-2);font-size:15rpx; }
.footer {
  position:fixed;left:0;right:0;bottom:0;z-index:10;display:flex;align-items:center;justify-content:space-between;
  padding:18rpx 28rpx calc(18rpx + env(safe-area-inset-bottom));border-top:1rpx solid var(--line);
  background:rgba(255,255,255,.96);backdrop-filter:blur(18rpx);
}
.pay-label { display:block;color:var(--muted);font-size:18rpx; }
.total { display:block;margin-top:2rpx;font-size:36rpx;font-weight:850;letter-spacing:-1rpx; }
.buy {
  width:310rpx;height:84rpx;margin:0;line-height:84rpx;border-radius:25rpx;background:var(--ink);color:#fff;
  font-size:25rpx;font-weight:780;
}
.buy[disabled]{opacity:.4}
</style>
