import { getDemoIdentities } from "../api/demo"

export type ProductPrincipal = {
  userId: string
}

export type CustomerPrincipal = ProductPrincipal & {
  nickname: string
}

export type PlayerPrincipal = ProductPrincipal & {
  playerId: string
  displayName: string
}

export async function getCustomerPrincipal(): Promise<CustomerPrincipal> {
  const identities = await getDemoIdentities()
  return {
    userId: identities.customer.userId,
    nickname: identities.customer.nickname
  }
}

export async function getPlayerPrincipal(): Promise<PlayerPrincipal | null> {
  const identities = await getDemoIdentities()
  const player = identities.players[0]
  return player
    ? {
        userId: player.userId,
        playerId: player.playerId,
        displayName: player.displayName
      }
    : null
}
