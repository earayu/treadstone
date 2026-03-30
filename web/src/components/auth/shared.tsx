export function GitHubGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="currentColor"
        d="M12 .5C5.65.5.5 5.65.5 12a11.5 11.5 0 0 0 7.86 10.9c.58.11.79-.25.79-.55 0-.27-.01-1.16-.01-2.1-3.2.7-3.87-1.37-4.12-2.61-.14-.35-.74-1.44-1.27-1.73-.43-.23-1.05-.8-.01-.82.97-.02 1.66.9 1.89 1.27 1.1 1.85 2.86 1.33 3.56 1.01.11-.8.43-1.33.78-1.64-2.73-.31-5.6-1.37-5.6-6.08 0-1.34.48-2.44 1.27-3.3-.13-.31-.55-1.57.12-3.28 0 0 1.03-.33 3.38 1.26a11.5 11.5 0 0 0 6.02 0c2.35-1.59 3.38-1.26 3.38-1.26.67 1.71.25 2.97.12 3.28.79.86 1.27 1.96 1.27 3.3 0 4.72-2.87 5.76-5.61 6.07.44.38.83 1.13.83 2.28 0 1.65-.02 2.98-.02 3.38 0 .33.21.67.8.56A11.5 11.5 0 0 0 23.5 12C23.5 5.65 18.35.5 12 .5Z"
      />
    </svg>
  )
}

export function GoogleGlyph({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" aria-hidden>
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  )
}

export function OAuthDivider({ label }: { label: string }) {
  return (
    <div className="relative my-8">
      <div className="absolute inset-0 flex items-center" aria-hidden>
        <span className="w-full border-t border-border" />
      </div>
      <div className="relative flex justify-center text-[10px] font-semibold uppercase tracking-[0.2em]">
        <span className="bg-background px-3 text-muted-foreground">{label}</span>
      </div>
    </div>
  )
}
