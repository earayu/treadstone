/** Home page SEO — English copy for public index + JSON-LD (AGENTS.md: public-facing marketing content in English). */

export const LANDING_SITE_URL = "https://treadstone-ai.dev"

export const LANDING_PAGE_TITLE =
  "Treadstone — Agent-native sandboxes for AI agents | CLI, SDK & REST API"

/** ~155 chars — primary keywords without stuffing */
export const LANDING_META_DESCRIPTION =
  "Isolated sandboxes for AI agents: control plane via CLI, Python SDK, or REST. Reach workloads over HTTP proxy, browser hand-off, and MCP—metered free tier."

const LANDING_JSONLD_SCRIPT_ID = "treadstone-landing-jsonld"

/** Injects JSON-LD into document head; remove on cleanup when leaving the home route (SPA). */
export function attachLandingJsonLd(): () => void {
  const existing = document.getElementById(LANDING_JSONLD_SCRIPT_ID)
  if (existing) existing.remove()
  const script = document.createElement("script")
  script.id = LANDING_JSONLD_SCRIPT_ID
  script.type = "application/ld+json"
  script.textContent = JSON.stringify(buildLandingJsonLd())
  document.head.appendChild(script)
  return () => {
    document.getElementById(LANDING_JSONLD_SCRIPT_ID)?.remove()
  }
}

export function buildLandingJsonLd(): Record<string, unknown> {
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Treadstone",
    applicationCategory: "DeveloperApplication",
    operatingSystem: "Cross-platform",
    description: LANDING_META_DESCRIPTION,
    url: `${LANDING_SITE_URL}/`,
    license: "https://www.apache.org/licenses/LICENSE-2.0",
    isAccessibleForFree: true,
    offers: {
      "@type": "Offer",
      price: "0",
      priceCurrency: "USD",
      description: "Free trial with metered compute (CU-hours)",
    },
    sameAs: ["https://x.com/treadstone_ai", "https://discord.gg/ygSP9tT5RB"],
  }
}
