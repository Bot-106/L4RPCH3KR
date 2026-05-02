import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import jsQR from 'jsqr'
import { Button } from '@/components/Button'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { consumePairing } from '@/lib/api'
import { useSessionStore } from '@/stores/sessionStore'
import { useAuthStore } from '@/stores/authStore'
import { getSession } from '@/lib/api'
import { colors } from '@/theme/tokens'

type Phase = 'requesting' | 'scanning' | 'processing' | 'done' | 'error'

export function ScanQrScreen() {
  const navigate = useNavigate()
  const setSession = useSessionStore((s) => s.setSession)
  const user = useAuthStore((s) => s.user)
  const [phase, setPhase] = useState<Phase>('requesting')
  const [error, setError] = useState('')
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const rafRef = useRef<number | null>(null)
  const processingRef = useRef(false)

  const stopCamera = useCallback(() => {
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
  }, [])

  const handleToken = useCallback(async (token: string) => {
    if (processingRef.current) return
    processingRef.current = true
    stopCamera()
    setPhase('processing')
    try {
      const res = await consumePairing(token)
      const sessionRes = await getSession(res.session_id)
      setSession(sessionRes.session)
      setPhase('done')
    } catch {
      setError('Invalid or expired QR code. Ask your partner to regenerate it.')
      setPhase('error')
      processingRef.current = false
    }
  }, [stopCamera, setSession])

  const startScan = useCallback(async () => {
    setError('')
    setPhase('requesting')
    processingRef.current = false
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setPhase('scanning')

      function tick() {
        const video = videoRef.current
        const canvas = canvasRef.current
        if (!video || !canvas || processingRef.current) return

        if (video.readyState === video.HAVE_ENOUGH_DATA) {
          canvas.width = video.videoWidth
          canvas.height = video.videoHeight
          const ctx = canvas.getContext('2d')
          if (ctx) {
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
            const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height)
            const code = jsQR(imageData.data, canvas.width, canvas.height, {
              inversionAttempts: 'dontInvert',
            })
            if (code) {
              void handleToken(code.data)
              return
            }
          }
        }
        rafRef.current = requestAnimationFrame(tick)
      }

      rafRef.current = requestAnimationFrame(tick)
    } catch {
      setError('Camera access denied. Please allow camera access and try again.')
      setPhase('error')
    }
  }, [handleToken])

  useEffect(() => {
    void startScan()
    return stopCamera
  }, [startScan, stopCamera])

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col">
      <div className="flex items-center gap-3 px-6 pt-safe-top pt-6 pb-4 border-b border-border-default">
        <button
          onClick={() => { stopCamera(); navigate(-1) }}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          ←
        </button>
        <h2 className="text-lg font-bold text-text-primary">Scan partner QR</h2>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-6">
        {(phase === 'scanning' || phase === 'requesting') && (
          <>
            <div className="relative w-full max-w-sm aspect-square rounded-lg overflow-hidden bg-black">
              <video
                ref={videoRef}
                className="absolute inset-0 w-full h-full object-cover"
                playsInline
                muted
              />
              {/* Targeting overlay */}
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                <div
                  className="w-48 h-48 border-2 rounded-lg"
                  style={{ borderColor: colors.accent.default }}
                />
              </div>
              {phase === 'requesting' && (
                <div className="absolute inset-0 flex items-center justify-center bg-bg-canvas/80">
                  <LoadingSpinner size="lg" />
                </div>
              )}
            </div>
            <canvas ref={canvasRef} className="hidden" />
            <p className="text-sm text-text-secondary text-center">
              Point camera at partner's QR code
            </p>
          </>
        )}

        {phase === 'processing' && (
          <div className="flex flex-col items-center gap-4">
            <LoadingSpinner size="lg" />
            <p className="text-sm text-text-secondary">Linking session…</p>
          </div>
        )}

        {phase === 'done' && (
          <div className="flex flex-col items-center gap-6">
            <div className="w-16 h-16 rounded-full bg-accent-default/20 flex items-center justify-center">
              <span className="text-3xl">✓</span>
            </div>
            <div className="flex flex-col items-center gap-2">
              <p className="text-md font-semibold text-text-primary">Partner linked</p>
              <p className="text-sm text-text-secondary">Session is active.</p>
            </div>
            <Button onClick={() => navigate('/live')} fullWidth>
              Go to live view
            </Button>
          </div>
        )}

        {phase === 'error' && (
          <div className="flex flex-col items-center gap-6 w-full max-w-sm">
            <p className="text-sm text-severity-high bg-severity-high/10 border border-severity-high/20 rounded-md px-4 py-3 w-full text-center">
              {error}
            </p>
            <Button onClick={startScan} fullWidth>
              Try again
            </Button>
            <Button variant="ghost" onClick={() => navigate(-1)} fullWidth>
              Go back
            </Button>
          </div>
        )}

        {/* Hide user info hint - only shown during active scan */}
        {phase === 'scanning' && user && (
          <p className="text-xs text-text-muted">
            Scanning as {user.display_name ?? user.email}
          </p>
        )}
      </div>
    </div>
  )
}
