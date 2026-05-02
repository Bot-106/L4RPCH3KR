import { forwardRef } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  fullWidth?: boolean
}

const variantClasses: Record<Variant, string> = {
  primary:   'bg-accent-default hover:bg-accent-strong text-text-inverse font-semibold',
  secondary: 'bg-bg-raised border border-border-default hover:border-border-strong text-text-primary font-medium',
  ghost:     'bg-transparent hover:bg-bg-raised text-text-secondary hover:text-text-primary font-medium',
  danger:    'bg-severity-high/10 hover:bg-severity-high/20 text-severity-high border border-severity-high/30 font-medium',
}

const sizeClasses: Record<Size, string> = {
  sm: 'px-3 py-1 text-sm rounded-md',
  md: 'px-4 py-3 text-md rounded-md',
  lg: 'px-6 py-4 text-lg rounded-lg',
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', size = 'md', loading = false, fullWidth = false, className = '', children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled ?? loading}
        className={[
          'inline-flex items-center justify-center gap-2 transition-all duration-fast select-none',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-default focus-visible:ring-offset-2 focus-visible:ring-offset-bg-canvas',
          'disabled:opacity-40 disabled:cursor-not-allowed',
          'active:scale-[0.97]',
          variantClasses[variant],
          sizeClasses[size],
          fullWidth ? 'w-full' : '',
          className,
        ].join(' ')}
        {...props}
      >
        {loading && (
          <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
        )}
        {children}
      </button>
    )
  },
)

Button.displayName = 'Button'
