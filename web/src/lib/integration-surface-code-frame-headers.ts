/**
 * Code frame header lines for the three integration surfaces (matches Landing "Three ways in").
 * Shown in every fenced block under that path so install hints stay consistent.
 */
export const INTEGRATION_SURFACE_CODE_FRAME_HEADERS = {
  cli: "bash — pip install treadstone-cli",
  sdk: "python — pip install treadstone-sdk",
  rest: "bash — REST API",
} as const

export type IntegrationSurface = keyof typeof INTEGRATION_SURFACE_CODE_FRAME_HEADERS
