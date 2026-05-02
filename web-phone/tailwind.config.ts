import type { Config } from 'tailwindcss'

const config: Config = {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          canvas: 'var(--color-bg-canvas)',
          surface: 'var(--color-bg-surface)',
          raised: 'var(--color-bg-raised)',
        },
        text: {
          primary: 'var(--color-text-primary)',
          secondary: 'var(--color-text-secondary)',
          muted: 'var(--color-text-muted)',
          inverse: 'var(--color-text-inverse)',
        },
        border: {
          default: 'var(--color-border-default)',
          strong: 'var(--color-border-strong)',
        },
        accent: {
          default: 'var(--color-accent-default)',
          strong: 'var(--color-accent-strong)',
        },
        severity: {
          low: 'var(--color-severity-low)',
          medium: 'var(--color-severity-medium)',
          high: 'var(--color-severity-high)',
        },
        status: {
          recording: 'var(--color-status-recording)',
          armed: 'var(--color-status-armed)',
          offline: 'var(--color-status-offline)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      fontSize: {
        xs:  ['12px', { lineHeight: '1.45' }],
        sm:  ['14px', { lineHeight: '1.45' }],
        md:  ['16px', { lineHeight: '1.45' }],
        lg:  ['18px', { lineHeight: '1.2' }],
        xl:  ['22px', { lineHeight: '1.2' }],
        '2xl': ['28px', { lineHeight: '1.2' }],
        '3xl': ['36px', { lineHeight: '1.2' }],
      },
      borderRadius: {
        sm:   '6px',
        md:   '10px',
        lg:   '16px',
        full: '999px',
      },
      spacing: {
        '0':  '0px',
        '1':  '4px',
        '2':  '8px',
        '3':  '12px',
        '4':  '16px',
        '6':  '24px',
        '8':  '32px',
        '12': '48px',
        '16': '64px',
        '24': '96px',
      },
      boxShadow: {
        sm: '0 1px 2px rgba(0,0,0,0.2)',
        md: '0 4px 12px rgba(0,0,0,0.25)',
        lg: '0 12px 32px rgba(0,0,0,0.35)',
      },
      animation: {
        'pulse-ring': 'pulse-ring 1.5s cubic-bezier(0.215, 0.61, 0.355, 1) infinite',
        'border-pulse': 'border-pulse 1s ease-in-out infinite',
      },
      keyframes: {
        'pulse-ring': {
          '0%': { transform: 'scale(0.95)', boxShadow: '0 0 0 0 rgba(255, 77, 77, 0.7)' },
          '70%': { transform: 'scale(1)', boxShadow: '0 0 0 10px rgba(255, 77, 77, 0)' },
          '100%': { transform: 'scale(0.95)', boxShadow: '0 0 0 0 rgba(255, 77, 77, 0)' },
        },
        'border-pulse': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
      },
    },
  },
  plugins: [],
}

export default config
