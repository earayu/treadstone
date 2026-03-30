/**
 * Format a duration given in minutes into a compact, human-readable string.
 * Examples: 5 → "5 min", 90 → "1.5 hr", 1440 → "1 day", 10080 → "7 days"
 */
export function formatMinutes(minutes: number): string {
  if (minutes === 0) return "Never"
  if (minutes < 0) return "—"
  if (minutes < 60) return `${minutes} min`
  const hours = minutes / 60
  if (hours < 24) return hours % 1 === 0 ? `${hours} hr` : `${hours.toFixed(1)} hr`
  const days = hours / 24
  return days % 1 === 0 ? `${days} day${days === 1 ? "" : "s"}` : `${days.toFixed(1)} days`
}

/**
 * Format a duration given in seconds into a compact, human-readable string.
 * Examples: 30 → "30 sec", 3600 → "1 hr", 86400 → "1 day", 0 → "Never"
 */
export function formatSeconds(seconds: number): string {
  if (seconds === 0) return "Never"
  if (seconds < 0) return "—"
  if (seconds < 60) return `${seconds} sec`
  return formatMinutes(Math.round(seconds / 60))
}
