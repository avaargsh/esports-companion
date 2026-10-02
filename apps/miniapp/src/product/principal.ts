import { getDemoIdentities } from "../api/demo"

export type ProductPrincipal = {
  userId: string
}

export async function getCustomerPrincipal(): Promise<ProductPrincipal> {
  const identities = await getDemoIdentities()
  return { userId: identities.customer.userId }
}

export async function getPlayerPrincipal(): Promise<ProductPrincipal | null> {
  const identities = await getDemoIdentities()
  const player = identities.players[0]
  return player ? { userId: player.userId } : null
}
