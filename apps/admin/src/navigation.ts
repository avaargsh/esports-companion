export type AdminSection =
  | "dashboard"
  | "orders"
  | "players"
  | "finance"
  | "config"

export const ADMIN_NAV = [
  {
    key: "dashboard" as const,
    label: "概览",
    description: "经营指标与待办队列",
    icon: "◫"
  },
  {
    key: "orders" as const,
    label: "订单",
    description: "交易履约、售后与证据",
    icon: "单"
  },
  {
    key: "players" as const,
    label: "陪玩",
    description: "身份与技能认证",
    icon: "人"
  },
  {
    key: "finance" as const,
    label: "资金",
    description: "提现与结算",
    icon: "¥"
  },
  {
    key: "config" as const,
    label: "配置",
    description: "游戏、服务与目录配置",
    icon: "设"
  }
] satisfies Array<{
  key: AdminSection
  label: string
  description: string
  icon: string
}>
