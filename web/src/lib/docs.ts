import { z } from "zod"

export const DOCS_SECTION_ORDER = [
  "Start Here",
  "Quickstarts",
  "Guides",
  "Reference",
  "Operations",
  "AI Docs",
] as const

const docsManifestEntrySchema = z.object({
  slug: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
  title: z.string().min(1),
  section: z.enum(DOCS_SECTION_ORDER),
  order: z.number().int().nonnegative(),
  summary: z.string().min(1),
  default: z.boolean(),
  llm_priority: z.number().int().nonnegative(),
})

const docsManifestSchema = z.array(docsManifestEntrySchema)

export type DocsManifestEntry = z.infer<typeof docsManifestEntrySchema>

export interface DocsSection {
  title: (typeof DOCS_SECTION_ORDER)[number]
  items: DocsManifestEntry[]
}

export function validateDocsManifest(data: unknown): DocsManifestEntry[] {
  const manifest = docsManifestSchema.parse(data)
  const seenSlugs = new Set<string>()
  const seenOrders = new Map<string, Set<number>>()
  let defaultCount = 0

  for (const entry of manifest) {
    if (seenSlugs.has(entry.slug)) {
      throw new Error(`Duplicate doc slug '${entry.slug}' in manifest.`)
    }
    seenSlugs.add(entry.slug)

    const sectionOrders = seenOrders.get(entry.section) ?? new Set<number>()
    if (sectionOrders.has(entry.order)) {
      throw new Error(`Duplicate order ${entry.order} in section '${entry.section}'.`)
    }
    sectionOrders.add(entry.order)
    seenOrders.set(entry.section, sectionOrders)

    if (entry.default) {
      defaultCount += 1
    }
  }

  if (defaultCount !== 1) {
    throw new Error("Docs manifest must define exactly one default page.")
  }

  return [...manifest].sort((left, right) => {
    const bySection = DOCS_SECTION_ORDER.indexOf(left.section) - DOCS_SECTION_ORDER.indexOf(right.section)
    if (bySection !== 0) {
      return bySection
    }
    if (left.order !== right.order) {
      return left.order - right.order
    }
    return left.slug.localeCompare(right.slug)
  })
}

export async function fetchDocsManifest(): Promise<DocsManifestEntry[]> {
  const response = await fetch("/docs/_manifest.json")
  if (!response.ok) {
    throw new Error(`Failed to load docs manifest: ${response.status}`)
  }
  return validateDocsManifest(await response.json())
}

export function groupDocsBySection(entries: DocsManifestEntry[]): DocsSection[] {
  return DOCS_SECTION_ORDER.map((section) => ({
    title: section,
    items: entries.filter((entry) => entry.section === section),
  })).filter((section) => section.items.length > 0)
}

export function getDefaultDoc(entries: DocsManifestEntry[]): DocsManifestEntry {
  const entry = entries.find((candidate) => candidate.default)
  if (!entry) {
    throw new Error("Docs manifest is missing a default page.")
  }
  return entry
}

export function resolveCurrentDoc(entries: DocsManifestEntry[], pageParam: string | null): DocsManifestEntry {
  return entries.find((entry) => entry.slug === pageParam) ?? getDefaultDoc(entries)
}

export function getAdjacentDocs(
  entries: DocsManifestEntry[],
  currentSlug: string,
): { previous: DocsManifestEntry | null; next: DocsManifestEntry | null } {
  const currentIndex = entries.findIndex((entry) => entry.slug === currentSlug)
  if (currentIndex === -1) {
    return { previous: null, next: null }
  }

  return {
    previous: entries[currentIndex - 1] ?? null,
    next: entries[currentIndex + 1] ?? null,
  }
}
