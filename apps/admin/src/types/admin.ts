export type Player = {
  id: string
  userId: string
  displayName: string
  verificationStatus: string
  serviceStatus: string
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

export type ReviewAction = "approve" | "reject"
