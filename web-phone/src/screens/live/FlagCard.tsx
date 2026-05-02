import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { colors } from '@/theme/tokens'
import type { LiveFlag } from '@/stores/sessionStore'

const AUTO_DISMISS_MS = 8000

interface FlagCardProps {
  liveFlag: LiveFlag
  onDismiss: () => void
}

export function FlagCard({ liveFlag, onDismiss }: FlagCardProps) {
  const { flag, claim, utterance } = liveFlag
  const [locked, setLocked] = useState(false)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Keep a stable ref to onDismiss so the auto-dismiss effect doesn't
  // restart the 8s countdown every time the parent re-renders (which would
  // produce a new inline function reference and retrigger the effect).
  const onDismissRef = useRef(onDismiss)
  useEffect(() => { onDismissRef.current = onDismiss })

  const borderColor = colors.severity[flag.severity]

  useEffect(() => {
    if (locked) {
      if (timerRef.current) clearTimeout(timerRef.current)
      return
    }
    timerRef.current = setTimeout(() => onDismissRef.current(), AUTO_DISMISS_MS)
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [locked])

  function handleTap() {
    if (!locked) {
      setLocked(true)
    } else {
      onDismiss()
    }
  }

  const severityLabel: Record<string, string> = {
    low: 'LOW',
    medium: 'MED',
    high: 'HIGH',
  }

  return (
    <motion.div
      layout
      initial={{ x: 100, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: 100, opacity: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
      onClick={handleTap}
      className={[
        'w-72 rounded-lg p-4 cursor-pointer select-none',
        'bg-bg-surface border-2 shadow-lg',
        !locked ? 'animate-border-pulse' : '',
      ].join(' ')}
      style={{ borderColor }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2">
          <span
            className="text-xs font-bold px-2 py-0.5 rounded-full"
            style={{
              background: `${borderColor}20`,
              color: borderColor,
              border: `1px solid ${borderColor}40`,
            }}
          >
            {severityLabel[flag.severity] ?? flag.severity.toUpperCase()}
          </span>
          <span className="text-xs text-text-muted">
            {Math.round(flag.confidence * 100)}% confidence
          </span>
        </div>
        <button
          onClick={(e) => { e.stopPropagation(); onDismiss() }}
          className="text-text-muted hover:text-text-secondary text-lg leading-none flex-shrink-0"
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>

      <p className="text-sm font-semibold text-text-primary mb-1 leading-snug">
        {flag.verified_text}
      </p>

      <p className="text-xs text-text-secondary leading-snug mb-3 line-clamp-2">
        "{utterance.text}"
      </p>

      <div className="flex items-center justify-between">
        <span className="text-xs text-text-muted capitalize">
          {claim.kind.replace(/_/g, ' ')} · {claim.subject}
        </span>
        {locked ? (
          <span className="text-xs text-text-muted">tap to dismiss</span>
        ) : (
          <span className="text-xs text-text-muted">tap to lock</span>
        )}
      </div>
    </motion.div>
  )
}
