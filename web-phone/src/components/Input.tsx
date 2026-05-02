import { forwardRef } from 'react'

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, className = '', id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label htmlFor={inputId} className="text-sm text-text-secondary font-medium">
            {label}
          </label>
        )}
        <input
          ref={ref}
          id={inputId}
          className={[
            'w-full bg-bg-raised border rounded-md px-4 py-3 text-md text-text-primary placeholder:text-text-muted',
            'outline-none transition-all duration-fast',
            'focus:ring-2 focus:ring-accent-default focus:border-transparent',
            error
              ? 'border-severity-high'
              : 'border-border-default hover:border-border-strong',
            className,
          ].join(' ')}
          {...props}
        />
        {error && <p className="text-xs text-severity-high">{error}</p>}
        {hint && !error && <p className="text-xs text-text-muted">{hint}</p>}
      </div>
    )
  },
)

Input.displayName = 'Input'
