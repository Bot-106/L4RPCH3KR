import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Button } from '@/components/Button'
import { disputeFlag } from '@/lib/api'
import type { Flag } from '@/contracts/types'

interface DisputeSheetProps {
  flag: Flag
  open: boolean
  onClose: () => void
  onDisputeSuccess: (updatedFlag: Flag) => void
}

export function DisputeSheet({ flag, open, onClose, onDisputeSuccess }: DisputeSheetProps) {
  const [reason, setReason] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!reason.trim()) return
    setError('')
    setLoading(true)
    try {
      const res = await disputeFlag(flag.id, reason.trim())
      onDisputeSuccess(res.flag)
      onClose()
    } catch {
      setError('Could not submit dispute. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-40"
            onClick={onClose}
          />
          {/* Sheet */}
          <motion.div
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed bottom-0 left-0 right-0 z-50 bg-bg-surface border-t border-border-default rounded-t-lg p-6 pb-safe-bottom"
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-md font-semibold text-text-primary">Dispute flag</h3>
              <button
                onClick={onClose}
                className="text-text-muted hover:text-text-secondary text-xl leading-none"
              >
                ×
              </button>
            </div>

            <div className="bg-bg-raised rounded-md p-3 mb-4">
              <p className="text-xs text-text-muted mb-1">Flag</p>
              <p className="text-sm text-text-primary">{flag.verified_text}</p>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <label className="text-sm text-text-secondary font-medium">
                  Why is this incorrect?
                </label>
                <textarea
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Explain why the flag is wrong…"
                  rows={3}
                  className="w-full bg-bg-raised border border-border-default hover:border-border-strong focus:ring-2 focus:ring-accent-default focus:border-transparent rounded-md px-4 py-3 text-md text-text-primary placeholder:text-text-muted outline-none resize-none transition-all"
                />
              </div>

              {error && (
                <p className="text-sm text-severity-high">{error}</p>
              )}

              <div className="flex gap-3">
                <Button type="button" variant="secondary" onClick={onClose} fullWidth>
                  Cancel
                </Button>
                <Button type="submit" loading={loading} disabled={!reason.trim()} fullWidth>
                  Submit
                </Button>
              </div>
            </form>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
