/**
 * Human-readable tier names for UI (API still uses short keys: free, pro, ultra, custom).
 */
const TIER_DISPLAY: Record<string, string> = {
  free: "Free",
  pro: "Pro",
  ultra: "Ultra",
  custom: "Custom Plan",
}

export function formatTierDisplayName(tier: string): string {
  return TIER_DISPLAY[tier] ?? (tier ? tier.charAt(0).toUpperCase() + tier.slice(1) : tier)
}
