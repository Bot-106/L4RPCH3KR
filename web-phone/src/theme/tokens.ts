// Values extracted from design/tokens/tokens.example.json
// CSS custom properties are set in src/main.tsx via injectTokens()

export const colors = {
  bg: {
    canvas:  '#0A0A0B',
    surface: '#141416',
    raised:  '#1C1C1F',
  },
  text: {
    primary:   '#F5F5F6',
    secondary: '#A1A1A8',
    muted:     '#5A5A62',
    inverse:   '#0A0A0B',
  },
  border: {
    default: '#27272B',
    strong:  '#3D3D43',
  },
  accent: {
    default: '#7C5CFF',
    strong:  '#5B3CE6',
  },
  severity: {
    low:    '#FFD166',
    medium: '#FF8A4C',
    high:   '#FF4D4D',
  },
  status: {
    recording: '#FF4D4D',
    armed:     '#7C5CFF',
    offline:   '#5A5A62',
  },
} as const

export const font = {
  family: {
    sans: 'Inter, system-ui, sans-serif',
    mono: 'JetBrains Mono, ui-monospace, monospace',
  },
  size: {
    xs:  12,
    sm:  14,
    md:  16,
    lg:  18,
    xl:  22,
    '2xl': 28,
    '3xl': 36,
  },
  weight: {
    regular:  400,
    medium:   500,
    semibold: 600,
    bold:     700,
  },
  lineHeight: {
    tight:   1.2,
    normal:  1.45,
    relaxed: 1.6,
  },
} as const

export const spacing = {
  0:   0,
  1:   4,
  2:   8,
  3:   12,
  4:   16,
  6:   24,
  8:   32,
  12:  48,
  16:  64,
  24:  96,
} as const

export const radius = {
  sm:   6,
  md:   10,
  lg:   16,
  full: 999,
} as const

export const shadow = {
  sm: '0 1px 2px rgba(0,0,0,0.2)',
  md: '0 4px 12px rgba(0,0,0,0.25)',
  lg: '0 12px 32px rgba(0,0,0,0.35)',
} as const

export const motionTokens = {
  duration: {
    fast:   120,
    normal: 240,
    slow:   480,
  },
  easing: {
    standard:   [0.2, 0.0, 0.0, 1.0] as const,
    emphasized: [0.3, 0.0, 0.8, 0.15] as const,
  },
} as const

export type SeverityLevel = 'low' | 'medium' | 'high'
export type StatusType = 'recording' | 'armed' | 'offline'

export function severityColor(severity: SeverityLevel): string {
  return colors.severity[severity]
}

// Injects CSS custom properties onto :root so Tailwind can reference them
export function injectTokens(): void {
  const root = document.documentElement
  root.style.setProperty('--color-bg-canvas',        colors.bg.canvas)
  root.style.setProperty('--color-bg-surface',       colors.bg.surface)
  root.style.setProperty('--color-bg-raised',        colors.bg.raised)
  root.style.setProperty('--color-text-primary',     colors.text.primary)
  root.style.setProperty('--color-text-secondary',   colors.text.secondary)
  root.style.setProperty('--color-text-muted',       colors.text.muted)
  root.style.setProperty('--color-text-inverse',     colors.text.inverse)
  root.style.setProperty('--color-border-default',   colors.border.default)
  root.style.setProperty('--color-border-strong',    colors.border.strong)
  root.style.setProperty('--color-accent-default',   colors.accent.default)
  root.style.setProperty('--color-accent-strong',    colors.accent.strong)
  root.style.setProperty('--color-severity-low',     colors.severity.low)
  root.style.setProperty('--color-severity-medium',  colors.severity.medium)
  root.style.setProperty('--color-severity-high',    colors.severity.high)
  root.style.setProperty('--color-status-recording', colors.status.recording)
  root.style.setProperty('--color-status-armed',     colors.status.armed)
  root.style.setProperty('--color-status-offline',   colors.status.offline)
}
