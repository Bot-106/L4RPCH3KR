import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/Button'
import { Input } from '@/components/Input'
import { requestMagicLink } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

type Step = 'enter_email' | 'check_email'

const DEV_USER = {
  id: 'dev-user-01',
  email: 'dev@test.local',
  display_name: 'Dev User',
  created_at: new Date().toISOString(),
  voice_calibration_id: 'dev-cal-01',
  github_login: 'devuser',
}

export function SignInScreen() {
  const [email, setEmail] = useState('')
  const [step, setStep] = useState<Step>('enter_email')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  function handleDevBypass() {
    setAuth(DEV_USER, 'dev-fake-jwt')
    navigate('/live', { replace: true })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setError('')
    setLoading(true)
    try {
      await requestMagicLink(email.trim())
      setStep('check_email')
    } catch {
      setError('Could not send magic link. Check your email and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <h1 className="text-2xl font-bold text-text-primary tracking-tight">L4RPCH3KR</h1>
          <p className="text-md text-text-secondary">
            Catch the larpers.
          </p>
        </div>

        {step === 'enter_email' ? (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <Input
              label="Email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              error={error}
              autoFocus
              autoComplete="email"
              inputMode="email"
            />
            <Button type="submit" loading={loading} fullWidth>
              Send magic link
            </Button>
            {import.meta.env.DEV && (
              <Button variant="ghost" fullWidth onClick={handleDevBypass}>
                Dev bypass → skip to live mode
              </Button>
            )}
          </form>
        ) : (
          <div className="flex flex-col gap-6">
            <div className="bg-bg-surface border border-border-default rounded-lg p-6 flex flex-col gap-2">
              <p className="text-md font-semibold text-text-primary">Check your inbox</p>
              <p className="text-sm text-text-secondary">
                We sent a sign-in link to <span className="text-text-primary">{email}</span>. Tap the link in the email to continue.
              </p>
            </div>
            <Button
              variant="ghost"
              fullWidth
              onClick={() => {
                setStep('enter_email')
                setError('')
              }}
            >
              Use a different email
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
