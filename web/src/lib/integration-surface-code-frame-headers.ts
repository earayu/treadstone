/**
 * Code frame header lines for the three integration surfaces (matches Landing “Three ways in”).
 * Shown in every fenced block under that path so install hints stay consistent.
 */
export const INTEGRATION_SURFACE_CODE_FRAME_HEADERS = {
  cli: "Install cli: curl -fsSL https://treadstone-ai.dev/install.sh | sh",
  sdk: "Python SDK: pip install treadstone-sdk",
  rest: "RESTFUL API: https://api.treadstone-ai.dev/docs",
} as const

export type IntegrationSurface = keyof typeof INTEGRATION_SURFACE_CODE_FRAME_HEADERS
