export const inputClassName =
  "w-full rounded-md border border-border bg-card px-3 py-2.5 text-sm text-foreground shadow-sm transition-[color,box-shadow] outline-none placeholder:text-muted-foreground/40 focus:ring-1 focus:ring-ring"

export function oauthAuthorizeUrl(provider: "google" | "github", returnTo?: string | null): string {
  const base = `/v1/auth/${provider}/authorize`
  if (returnTo) return `${base}?return_to=${encodeURIComponent(returnTo)}`
  return base
}
