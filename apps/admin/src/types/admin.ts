export type Player = {
  id: string
  userId: string
  displayName: string
  verificationStatus: string
  verificationStatusCode: "PENDING" | "APPROVED" | "REJECTED" | "CANCELLED"
  serviceStatus: string
  serviceStatusCode: "AVAILABLE" | "OFFLINE" | "SUSPENDED"
  availableActions?: PlayerReviewAction[]
  rating: number
  orderCount: number
}

export type Order = {
  id: string
  orderNo: string
  userId: string
  status: string
  totalAmount: number
  version: number
  createdAt: string
}

export type PlayerSkillReview = {
  id: string
  playerId: string
  playerName: string
  gameId: string
  gameName: string
  rank: string | null
  description: string
  evidenceUrl: string | null
  verificationStatus: string
  verificationStatusCode: "PENDING" | "APPROVED" | "REJECTED" | "REVOKED"
  availableActions?: SkillReviewAction[]
  reviewNote: string
  updatedAt: string
}

export type Settlement = {
  id: string
  orderId: string
  playerId: string
  grossAmount: number
  playerAmount: number
  platformFee: number
  status: string
}

export type PlayerReviewAction = "APPROVE" | "REJECT" | "CANCEL" | "RESTORE"
export type SkillReviewAction = "APPROVE" | "REJECT" | "REVOKE"
export type ReviewAction = "approve" | "reject" | "cancel" | "restore" | "revoke"


export type AdminUser = {
  id: string
  openid: string | null
  unionid: string | null
  nickname: string
  avatarUrl: string | null
  phone: string | null
  role: string
  status: string
  statusCode: "ACTIVE" | "BLOCKED" | "INACTIVE"
  orderCount: number
  totalSpent: number
  availableBalance: number
  frozenBalance: number
  createdAt: string
  updatedAt: string
}

export type ConsumptionRecord = {
  id: string
  orderNo: string
  status: string
  statusCode: string
  amount: number
  platformFee: number
  playerAmount: number
  createdAt: string
  paidAt: string | null
  settledAt: string | null
}

export type OperationLog = {
  id: string
  source: string
  actorUserId: string
  action: string
  resourceType: string
  resourceId: string
  decision: string
  reason: string
  createdAt: string
}

export type Announcement = {
  id: string
  title: string
  content: string
  audience: string
  noticeType: "NORMAL" | "SYSTEM"
  noticeTypeText: string
  status: string
  statusCode: "DRAFT" | "PUBLISHED" | "OFFLINE"
  operatorUserId: string
  publishedAt: string | null
  createdAt: string
  updatedAt: string
}
