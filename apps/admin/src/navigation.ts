export type AdminSection =
  | "dashboard"
  | "orders"
  | "players"
  | "finance"
  | "config"
  | "users"
  | "marketing"
  | "system"

export type AdminNavChild = {
  label: string
  target: AdminSection
}

export const ADMIN_NAV = [
  {
    key: "dashboard" as const,
    label: "数据概览",
    description: "经营看板、运营待办与异常队列",
    iconUrl: "https://img.icons8.com/fluency/96/combo-chart.png",
    children: [
      { label: "经营看板", target: "dashboard" as const },
      { label: "运营待办与异常队列", target: "dashboard" as const }
    ]
  },
  {
    key: "orders" as const,
    label: "订单管理",
    description: "全部订单、售后退款仲裁与调配日志",
    iconUrl: "https://img.icons8.com/fluency/96/purchase-order.png",
    children: [
      { label: "全部订单列表", target: "orders" as const },
      { label: "售后/退款仲裁", target: "orders" as const },
      { label: "调配与改派日志", target: "orders" as const }
    ]
  },
  {
    key: "players" as const,
    label: "陪玩管理",
    description: "陪玩入驻、技能认证与推荐排序",
    iconUrl: "https://img.icons8.com/fluency/96/headset.png",
    children: [
      { label: "陪玩入驻审核", target: "players" as const },
      { label: "技能/段位认证", target: "players" as const },
      { label: "陪玩列表与封禁", target: "players" as const }
    ]
  },
  {
    key: "finance" as const,
    label: "资金与结算",
    description: "提现审核、服务费与财务流水",
    iconUrl: "https://img.icons8.com/fluency/96/wallet.png",
    children: [
      { label: "提现申请审核", target: "finance" as const },
      { label: "平台抽成设置", target: "finance" as const },
      { label: "财务流水明细", target: "finance" as const }
    ]
  },
  {
    key: "config" as const,
    label: "服务配置",
    description: "游戏分类、套餐定价与 Banner 管理",
    iconUrl: "https://img.icons8.com/fluency/96/services.png",
    children: [
      { label: "游戏分类配置", target: "config" as const },
      { label: "服务套餐定价", target: "config" as const },
      { label: "首页 Banner 管理", target: "config" as const }
    ]
  },
  {
    key: "users" as const,
    label: "用户管理",
    description: "玩家列表、余额记录与风控",
    iconUrl: "https://img.icons8.com/fluency/96/conference-call.png",
    children: [
      { label: "玩家列表", target: "users" as const },
      { label: "黑名单管理", target: "users" as const }
    ]
  },
  {
    key: "marketing" as const,
    label: "消息公告",
    description: "系统通知与广播推送",
    iconUrl: "https://img.icons8.com/fluency/96/appointment-reminders.png",
    children: [
      { label: "系统通知推送", target: "marketing" as const }
    ]
  },
  {
    key: "system" as const,
    label: "系统设置",
    description: "权限管理、操作日志与 Demo 模式",
    iconUrl: "https://img.icons8.com/fluency/96/administrative-tools.png",
    children: [
      { label: "权限管理", target: "system" as const },
      { label: "操作日志", target: "system" as const }
    ]
  }
] satisfies Array<{
  key: string
  label: string
  description: string
  iconUrl: string
  children: AdminNavChild[]
}>

export function isAdminSection(value: string): value is AdminSection {
  return ["dashboard", "orders", "players", "finance", "config", "users", "marketing", "system"].includes(value)
}
