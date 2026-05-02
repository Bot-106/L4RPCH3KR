import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { FlagDetail } from './FlagDetail'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { Button } from '@/components/Button'
import { getSessionRecap } from '@/lib/api'
import { colors } from '@/theme/tokens'
import type { Flag, Claim, Utterance } from '@/contracts/types'

interface SelectedFlag {
  flag: Flag
  claim: Claim
  utterance: Utterance
}

export function RecapScreen() {
  const { sessionId } = useParams<{ sessionId: string }>()
  const navigate = useNavigate()
  const [selected, setSelected] = useState<SelectedFlag | null>(null)
  const [localFlags, setLocalFlags] = useState<Flag[]>([])

  const { data, isLoading, error } = useQuery({
    queryKey: ['recap', sessionId],
    queryFn: () => getSessionRecap(sessionId!),
    enabled: Boolean(sessionId),
  })

  function handleFlagUpdate(updatedFlag: Flag) {
    setLocalFlags((prev) => {
      const exists = prev.find((f) => f.id === updatedFlag.id)
      if (exists) return prev.map((f) => f.id === updatedFlag.id ? updatedFlag : f)
      return [...prev, updatedFlag]
    })
  }

  if (isLoading) {
    return (
      <div className="min-h-screen bg-bg-canvas flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-bg-canvas flex flex-col items-center justify-center px-6 gap-4">
        <p className="text-sm text-severity-high">Could not load recap.</p>
        <Button variant="secondary" onClick={() => navigate(-1)}>Go back</Button>
      </div>
    )
  }

  const { session, partner, flags: rawFlags, claims, utterances, score } = data
  const mergedFlags = rawFlags.map((f) => localFlags.find((lf) => lf.id === f.id) ?? f)

  const duration = session.ended_at
    ? Math.round((new Date(session.ended_at).getTime() - new Date(session.started_at).getTime()) / 60000)
    : null

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 px-6 pt-safe-top pt-6 pb-4 border-b border-border-default">
        <button
          onClick={() => navigate(-1)}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          ←
        </button>
        <h2 className="text-lg font-bold text-text-primary">Session recap</h2>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Score section */}
        <div className="px-6 py-6 border-b border-border-default">
          <div className="flex items-center justify-between mb-4">
            <div className="flex flex-col gap-1">
              <p className="text-xs text-text-muted uppercase tracking-widest">Larp score</p>
              <p className="text-3xl font-bold text-text-primary font-mono">
                {(score * 100).toFixed(0)}
              </p>
            </div>
            {partner && (
              <div className="flex flex-col items-end gap-1">
                {partner.photo_url && (
                  <img
                    src={partner.photo_url}
                    alt={partner.full_name}
                    className="w-10 h-10 rounded-full object-cover"
                  />
                )}
                <p className="text-sm font-medium text-text-primary">{partner.full_name}</p>
                {partner.headline && (
                  <p className="text-xs text-text-muted">{partner.headline}</p>
                )}
              </div>
            )}
          </div>

          <div className="flex gap-4">
            <div className="flex flex-col gap-0.5">
              <p className="text-xs text-text-muted">Flags</p>
              <p className="text-md font-semibold text-text-primary">{mergedFlags.length}</p>
            </div>
            <div className="flex flex-col gap-0.5">
              <p className="text-xs text-text-muted">Claims</p>
              <p className="text-md font-semibold text-text-primary">{claims.length}</p>
            </div>
            {duration !== null && (
              <div className="flex flex-col gap-0.5">
                <p className="text-xs text-text-muted">Duration</p>
                <p className="text-md font-semibold text-text-primary">{duration}m</p>
              </div>
            )}
          </div>
        </div>

        {/* Flags list */}
        <div className="px-6 py-4">
          {mergedFlags.length === 0 ? (
            <p className="text-sm text-text-muted text-center py-8">No flags raised in this session.</p>
          ) : (
            <div className="flex flex-col gap-3">
              <p className="text-xs text-text-muted uppercase tracking-wide mb-1">Flags</p>
              {mergedFlags.map((flag) => {
                const claim = claims.find((c) => c.id === flag.claim_id)
                const utterance = claim ? utterances.find((u) => u.id === claim.utterance_id) : undefined
                if (!claim || !utterance) return null

                const borderColor = colors.severity[flag.severity]

                return (
                  <button
                    key={flag.id}
                    onClick={() => setSelected({ flag, claim, utterance })}
                    className="w-full text-left bg-bg-surface border rounded-lg p-4 transition-all hover:border-border-strong"
                    style={{ borderLeftWidth: 3, borderLeftColor: borderColor }}
                  >
                    <div className="flex items-start justify-between gap-2 mb-2">
                      <span
                        className="text-xs font-bold px-2 py-0.5 rounded-full uppercase"
                        style={{ background: `${borderColor}20`, color: borderColor }}
                      >
                        {flag.severity}
                      </span>
                      {flag.disputed && (
                        <span className="text-xs text-text-muted">Disputed</span>
                      )}
                    </div>
                    <p className="text-sm font-medium text-text-primary leading-snug mb-1">
                      {flag.verified_text}
                    </p>
                    <p className="text-xs text-text-muted line-clamp-1">
                      "{utterance.text}"
                    </p>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {selected && (
        <FlagDetail
          flag={selected.flag}
          claim={selected.claim}
          utterance={selected.utterance}
          open={true}
          onClose={() => setSelected(null)}
          onFlagUpdate={handleFlagUpdate}
        />
      )}
    </div>
  )
}
