import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/Button'
import { uploadVoiceCalibration, getMe } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'
import { colors } from '@/theme/tokens'

const RECORDING_DURATION = 15

type Phase = 'idle' | 'requesting' | 'recording' | 'uploading' | 'done' | 'error'

export function VoiceCalibrationScreen() {
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)
  const [phase, setPhase] = useState<Phase>('idle')
  const [secondsLeft, setSecondsLeft] = useState(RECORDING_DURATION)
  const [error, setError] = useState('')

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const streamRef = useRef<MediaStream | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop()
    }
    streamRef.current?.getTracks().forEach((t) => t.stop())
  }, [])

  async function startRecording() {
    setError('')
    setPhase('requesting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'

      const recorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = recorder
      chunksRef.current = []

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeType })
        setPhase('uploading')
        try {
          const res = await uploadVoiceCalibration(blob)
          // Update user in store with the new calibration id from getMe()
          const user = await getMe()
          setUser({ ...user, voice_calibration_id: res.calibration.id })
          setPhase('done')
        } catch {
          setError('Upload failed. Please try again.')
          setPhase('error')
        }
      }

      recorder.start(250)
      setPhase('recording')
      setSecondsLeft(RECORDING_DURATION)

      timerRef.current = setInterval(() => {
        setSecondsLeft((s) => {
          if (s <= 1) {
            stopRecording()
            return 0
          }
          return s - 1
        })
      }, 1000)
    } catch {
      setError('Microphone access denied. Please allow mic access and try again.')
      setPhase('error')
    }
  }

  const progress = ((RECORDING_DURATION - secondsLeft) / RECORDING_DURATION) * 100

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <div className="w-12 h-12 rounded-full bg-bg-raised flex items-center justify-center mb-2">
            <span className="text-2xl">🎙️</span>
          </div>
          <h2 className="text-xl font-bold text-text-primary">Voice calibration</h2>
          <p className="text-sm text-text-secondary">
            Speak naturally for 15 seconds so the system can distinguish your voice from your partner's.
          </p>
        </div>

        <div className="flex flex-col gap-6">
          {phase === 'recording' && (
            <div className="flex flex-col gap-3">
              <div className="flex justify-between items-center">
                <span className="text-sm text-text-secondary">Recording…</span>
                <span
                  className="text-sm font-mono font-medium"
                  style={{ color: colors.status.recording }}
                >
                  {secondsLeft}s
                </span>
              </div>
              <div className="h-1.5 bg-bg-raised rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-1000"
                  style={{
                    width: `${progress}%`,
                    background: colors.status.recording,
                  }}
                />
              </div>
              <div className="flex justify-center">
                <div
                  className="w-4 h-4 rounded-full animate-pulse-ring"
                  style={{ background: colors.status.recording }}
                />
              </div>
            </div>
          )}

          {phase === 'uploading' && (
            <div className="flex flex-col items-center gap-3 py-4">
              <div className="w-8 h-8 border-2 border-accent-default border-t-transparent rounded-full animate-spin" />
              <p className="text-sm text-text-secondary">Uploading calibration…</p>
            </div>
          )}

          {phase === 'done' && (
            <div className="bg-accent-default/10 border border-accent-default/20 rounded-lg p-4 flex flex-col gap-1">
              <p className="text-sm font-semibold text-text-primary">Calibration complete</p>
              <p className="text-xs text-text-secondary">Your voice profile has been saved.</p>
            </div>
          )}

          {error && (
            <p className="text-sm text-severity-high bg-severity-high/10 border border-severity-high/20 rounded-md px-4 py-3">
              {error}
            </p>
          )}

          {(phase === 'idle' || phase === 'error') && (
            <Button onClick={startRecording} fullWidth>
              Start recording
            </Button>
          )}

          {phase === 'recording' && (
            <Button variant="secondary" onClick={stopRecording} fullWidth>
              Stop early
            </Button>
          )}

          {phase === 'done' && (
            <Button onClick={() => navigate('/onboarding/pair')} fullWidth>
              Continue
            </Button>
          )}

          {phase !== 'done' && (
            <Button
              variant="ghost"
              fullWidth
              onClick={() => navigate('/onboarding/pair')}
            >
              Skip for now
            </Button>
          )}
        </div>

        <p className="text-xs text-text-muted text-center">
          Step 3 of 4 — Voice calibration
        </p>
      </div>
    </div>
  )
}
