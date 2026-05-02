import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { DisputeSheet } from './DisputeSheet'
import { colors } from '@/theme/tokens'
import type { Flag, Claim, Utterance } from '@/contracts/types'

interface FlagDetailProps {
  flag: Flag
  claim: Claim
  utterance: Utterance
  open: boolean
  onClose: () => void
  onFlagUpdate: (flag: Flag) => void
}

export function FlagDetail({ flag: initialFlag, claim, utterance, open, onClose, onFlagUpdate }: FlagDetailProps) {
  const [flag, setFlag] = useState(initialFlag)
  const [disputeOpen, setDisputeOpen] = useState(false)

  const borderColor = colors.severity[flag.severity]

  function handleDisputeSuccess(updated: Flag) {
    setFlag(updated)
    onFlagUpdate(updated)
  }

  return (
    <>
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/60 z-40"
              onClick={onClose}
            />
            <motion.div
              initial={{ y: '100%' }}
              animate={{ y: 0 }}
              exit={{ y: '100%' }}
              transition={{ type: 'spring', stiffness: 300, damping: 30 }}
              className="fixed bottom-0 left-0 right-0 z-50 bg-bg-surface border-t border-border-default rounded-t-lg max-h-[85vh] overflow-y-auto"
            >
              <div
                className="border-t-4 rounded-t-lg px-6 pt-5 pb-6"
                style={{ borderColor }}
              >
                <div className="flex items-start justify-between mb-4">
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <span
                        className="text-xs font-bold px-2 py-0.5 rounded-full uppercase"
                        style={{ background: `${borderColor}20`, color: borderColor, border: `1px solid ${borderColor}40` }}
                      >
                        {flag.severity}
                      </span>
                      {flag.disputed && (
                        <span className="text-xs text-text-muted bg-bg-raised px-2 py-0.5 rounded-full">
                          Disputed
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    onClick={onClose}
                    className="text-text-muted hover:text-text-secondary text-xl leading-none"
                  >
                    ×
                  </button>
                </div>

                {/* Flag text */}
                <p className="text-md font-semibold text-text-primary mb-4 leading-snug">
                  {flag.verified_text}
                </p>

                {/* Claim */}
                <div className="bg-bg-raised rounded-md p-3 mb-3">
                  <p className="text-xs text-text-muted mb-1 uppercase tracking-wide">Claim</p>
                  <p className="text-sm text-text-secondary">
                    <span className="text-text-primary">{claim.subject}</span>
                    {' · '}{claim.kind.replace(/_/g, ' ')}
                    {' · '}{claim.hedge !== 'none' ? `${claim.hedge} hedge` : 'no hedge'}
                  </p>
                </div>

                {/* Utterance */}
                <div className="bg-bg-raised rounded-md p-3 mb-3">
                  <p className="text-xs text-text-muted mb-1 uppercase tracking-wide">What was said</p>
                  <p className="text-sm text-text-secondary italic">"{utterance.text}"</p>
                  {utterance.audio_url && (
                    <audio
                      src={utterance.audio_url}
                      controls
                      className="w-full mt-3 h-8"
                    />
                  )}
                </div>

                {/* Stats */}
                <div className="flex gap-4 mb-4">
                  <div className="flex flex-col gap-0.5">
                    <p className="text-xs text-text-muted">Confidence</p>
                    <p className="text-sm font-semibold text-text-primary">
                      {Math.round(flag.confidence * 100)}%
                    </p>
                  </div>
                  <div className="flex flex-col gap-0.5">
                    <p className="text-xs text-text-muted">Score delta</p>
                    <p className="text-sm font-semibold" style={{ color: borderColor }}>
                      +{flag.score_delta.toFixed(2)}
                    </p>
                  </div>
                </div>

                {flag.dispute_reason && (
                  <div className="bg-accent-default/10 border border-accent-default/20 rounded-md p-3 mb-4">
                    <p className="text-xs text-text-muted mb-1">Dispute reason</p>
                    <p className="text-sm text-text-secondary">{flag.dispute_reason}</p>
                  </div>
                )}

                {!flag.disputed && (
                  <button
                    onClick={() => setDisputeOpen(true)}
                    className="w-full text-sm text-text-muted hover:text-text-secondary py-2 border border-border-default rounded-md transition-colors"
                  >
                    Dispute this flag
                  </button>
                )}
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>

      <DisputeSheet
        flag={flag}
        open={disputeOpen}
        onClose={() => setDisputeOpen(false)}
        onDisputeSuccess={handleDisputeSuccess}
      />
    </>
  )
}
