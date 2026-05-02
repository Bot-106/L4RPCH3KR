import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import { StatusPill } from './StatusPill'
import { FlagCard } from './FlagCard'
import { Button } from '@/components/Button'
import { useAuthStore } from '@/stores/authStore'
import { useSessionStore } from '@/stores/sessionStore'
import { wsClient } from '@/lib/ws'
import type { WsSessionStatus, WsFlagRaised, WsScoreUpdate } from '@/contracts/types'

export function LiveScreen() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const {
    session,
    wsStatus,
    sessionStatus,
    flags,
    score,
    setWsStatus,
    setSessionStatus,
    addFlag,
    dismissFlag,
  } = useSessionStore()

  const jwt = useAuthStore((s) => s.jwt)

  useEffect(() => {
    if (!jwt || !user) return

    wsClient.connect(jwt)
    setWsStatus('connecting')

    const offConnected = wsClient.on('connected', () => {
      setWsStatus('connected')
      wsClient.send('phone_hello', {
        user_id: user.id,
        app_version: '0.1.0',
      })
    })

    const offDisconnected = wsClient.on('disconnected', () => {
      setWsStatus('disconnected')
    })

    const offReconnecting = wsClient.on('reconnecting', () => {
      setWsStatus('reconnecting')
    })

    const offConnecting = wsClient.on('connecting', () => {
      setWsStatus('connecting')
    })

    const offSessionStatus = wsClient.on('session_status', (data) => {
      const payload = data as WsSessionStatus
      setSessionStatus(payload.status)
    })

    const offFlagRaised = wsClient.on('flag_raised', (data) => {
      const payload = data as WsFlagRaised
      addFlag(payload.flag, payload.claim, payload.utterance)
    })

    const offScoreUpdate = wsClient.on('score_update', (data) => {
      const payload = data as WsScoreUpdate
      useSessionStore.getState().setScore(payload.score)
    })

    return () => {
      offConnected()
      offDisconnected()
      offReconnecting()
      offConnecting()
      offSessionStatus()
      offFlagRaised()
      offScoreUpdate()
      wsClient.disconnect()
    }
  }, [jwt, user, setWsStatus, setSessionStatus, addFlag])

  // Subscribe to session when it becomes available
  useEffect(() => {
    if (session && wsStatus === 'connected') {
      wsClient.setSessionId(session.id)
      wsClient.send('subscribe_session', { session_id: session.id }, session.id)
    }
  }, [session, wsStatus])

  const visibleFlags = flags.filter((f) => !f.dismissed).slice(-3)

  const severities = ['low', 'medium', 'high'] as const
  function fireMockFlag() {
    const sev = severities[flags.length % 3]
    addFlag(
      {
        id: `mock-flag-${Date.now()}`,
        claim_id: 'mock-claim',
        profile_id: 'mock-profile',
        severity: sev,
        score_delta: 0.15,
        verified_text: sev === 'low'
          ? 'GitHub shows 2 Rust commits, not 5 years'
          : sev === 'medium'
          ? 'LinkedIn shows no employment at Google'
          : 'No MIT degree found in public records',
        confidence: 0.87,
        created_at: new Date().toISOString(),
        disputed: false,
        dispute_reason: null,
      },
      {
        id: `mock-claim-${Date.now()}`,
        utterance_id: 'mock-utt',
        kind: 'language_experience',
        subject: sev === 'low' ? 'Rust' : sev === 'medium' ? 'Google' : 'MIT',
        predicate: sev === 'low' ? 'experience_years' : sev === 'medium' ? 'worked_at' : 'graduated_from',
        value: {},
        hedge: 'none',
        extraction_confidence: 0.91,
        text_span: sev === 'low'
          ? "I've been writing Rust for 5 years"
          : sev === 'medium'
          ? "I worked at Google for two years"
          : "I went to MIT for my CS degree",
      },
      {
        id: `mock-utt-${Date.now()}`,
        session_id: 'mock-session',
        speaker: 'partner',
        speaker_confidence: 0.94,
        started_at: new Date().toISOString(),
        ended_at: new Date().toISOString(),
        text: sev === 'low'
          ? "I've been writing Rust for 5 years"
          : sev === 'medium'
          ? "I worked at Google for two years"
          : "I went to MIT for my CS degree",
        audio_url: null,
      },
    )
  }

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-6 pt-safe-top pt-6 pb-4 border-b border-border-default">
        <h1 className="text-lg font-bold text-text-primary tracking-tight">L4RPCH3KR</h1>
        <StatusPill sessionStatus={sessionStatus} wsStatus={wsStatus} />
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-8">
        {/* Score */}
        <div className="flex flex-col items-center gap-2">
          <p className="text-xs text-text-muted uppercase tracking-widest">Larp score</p>
          <p className="text-3xl font-bold text-text-primary font-mono">
            {(score * 100).toFixed(0)}
          </p>
          <p className="text-sm text-text-muted">
            {score === 0 ? 'No flags yet' : `${flags.length} flag${flags.length !== 1 ? 's' : ''} raised`}
          </p>
        </div>

        {/* Dev tools */}
        {import.meta.env.DEV && (
          <Button variant="secondary" size="sm" onClick={fireMockFlag}>
            🚩 Fire mock flag ({severities[flags.length % 3]})
          </Button>
        )}

        {/* Session info */}
        {session ? (
          <div className="w-full max-w-sm bg-bg-surface border border-border-default rounded-lg p-4 flex flex-col gap-2">
            <p className="text-xs text-text-muted uppercase tracking-wide">Session</p>
            <p className="text-sm font-mono text-text-secondary truncate">{session.id}</p>
            <div className="flex gap-2 mt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate('/pair/show')}
              >
                Show QR
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate('/pair/scan')}
              >
                Scan partner
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate(`/recap/${session.id}`)}
              >
                Recap
              </Button>
            </div>
          </div>
        ) : (
          <div className="w-full max-w-sm flex flex-col gap-3">
            <Button onClick={() => navigate('/pair/scan')} fullWidth>
              Scan partner QR
            </Button>
            <Button variant="secondary" onClick={() => navigate('/pair/show')} fullWidth>
              Show my QR
            </Button>
          </div>
        )}
      </div>

      {/* Bottom nav */}
      <div className="px-6 pb-safe-bottom pb-6 border-t border-border-default pt-4">
        <div className="flex items-center justify-between">
          <span className="text-xs text-text-muted">
            {user?.display_name ?? user?.email ?? '—'}
          </span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              wsClient.disconnect()
              clearAuth()
              navigate('/onboarding/signin', { replace: true })
            }}
          >
            Sign out
          </Button>
        </div>
      </div>

      {/* Flag cards overlay — bottom-right */}
      <div className="fixed bottom-24 right-4 flex flex-col gap-3 z-50 pointer-events-none">
        <AnimatePresence mode="popLayout">
          {visibleFlags.map((lf) => (
            <div key={lf.flag.id} className="pointer-events-auto">
              <FlagCard
                liveFlag={lf}
                onDismiss={() => dismissFlag(lf.flag.id)}
              />
            </div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
