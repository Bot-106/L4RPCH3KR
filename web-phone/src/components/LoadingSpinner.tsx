interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const sizeClasses = {
  sm: 'w-4 h-4 border-2',
  md: 'w-8 h-8 border-2',
  lg: 'w-12 h-12 border-[3px]',
}

export function LoadingSpinner({ size = 'md', className = '' }: LoadingSpinnerProps) {
  return (
    <div
      className={[
        'rounded-full border-accent-default border-t-transparent animate-spin',
        sizeClasses[size],
        className,
      ].join(' ')}
      role="status"
      aria-label="Loading"
    />
  )
}
