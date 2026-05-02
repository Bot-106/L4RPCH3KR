import { colors } from '@/theme/tokens'
import type { WsStatus, SessionStatus } from '@/stores/sessionStore'

interface StatusPillProps {
  sessionStatus: SessionStatus
  wsStatus: WsStatus
}

interface PillConfig {
  label: string
  color: string
  pulse: boolean
}

function getPillConfig(sessionStatus: SessionStatus, wsStatus: WsStatus): PillConfig {
  if (wsStatus === 'connecting' || wsStatus === 'reconnecting') {
    return { label: 'Connecting…', color: colors.status.offline, pulse: false }
  }
  if (wsStatus === 'disconnected') {
    return { label: 'Disconnected', color: colors.status.offline, pulse: false }
  }
  switch (sessionStatus) {
    case 'active':
      return { label: 'Recording', color: colors.status.recording, pulse: true }
    case 'armed':
      return { label: 'Armed', color: colors.status.armed, pulse: false }
    case 'ended':
      return { label: 'Ended', color: colors.status.offline, pulse: false }
    default:
      return { label: 'Connected', color: colors.status.offline, pulse: false }
  }
}

export function StatusPill({ sessionStatus, wsStatus }: StatusPillProps) {
  const { label, color, pulse } = getPillConfig(sessionStatus, wsStatus)

  return (
    <div
      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full"
      style={{ background: `${color}20`, border: `1px solid ${color}40` }}
    >
      <span
        className={`w-2 h-2 rounded-full flex-shrink-0 ${pulse ? 'animate-pulse' : ''}`}
        style={{ background: color }}
      />
      <span
        className="text-xs font-semibold tracking-wide uppercase"
        style={{ color }}
      >
        {label}
      </span>
    </div>
  )
}
