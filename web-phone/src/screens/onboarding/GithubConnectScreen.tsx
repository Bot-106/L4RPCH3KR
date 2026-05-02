import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/Button'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { getGithubStartUrl, getMe } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

export function GithubConnectScreen() {
  const navigate = useNavigate()
  const setUser = useAuthStore((s) => s.setUser)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Handle return from GitHub OAuth
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const code = params.get('code')
    if (!code) return

    // Clear the code from URL
    window.history.replaceState({}, '', window.location.pathname)

    async function finalize() {
      try {
        const user = await getMe()
        setUser(user)
        if (user.github_login) {
          navigate('/onboarding/voice')
        }
      } catch {
        setError('GitHub connection failed. Please try again.')
      }
    }

    void finalize()
  }, [navigate, setUser])

  async function handleConnect() {
    setError('')
    setLoading(true)
    try {
      const callbackUrl = `${window.location.origin}/onboarding/github`
      const url = await getGithubStartUrl(callbackUrl)
      window.location.href = url
    } catch {
      setError('Could not start GitHub sign-in. Try again.')
      setLoading(false)
    }
  }

  const params = new URLSearchParams(window.location.search)
  const isReturning = Boolean(params.get('code'))

  if (isReturning) {
    return (
      <div className="min-h-screen bg-bg-canvas flex items-center justify-center">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <div className="w-12 h-12 rounded-full bg-bg-raised flex items-center justify-center mb-2">
            <span className="text-2xl">🐙</span>
          </div>
          <h2 className="text-xl font-bold text-text-primary">Connect GitHub</h2>
          <p className="text-sm text-text-secondary">
            We use your GitHub profile to verify claims made in conversation. We only read public data.
          </p>
        </div>

        <div className="flex flex-col gap-3">
          {error && (
            <p className="text-sm text-severity-high bg-severity-high/10 border border-severity-high/20 rounded-md px-4 py-3">
              {error}
            </p>
          )}
          <Button onClick={handleConnect} loading={loading} fullWidth>
            Continue with GitHub
          </Button>
          <Button
            variant="ghost"
            fullWidth
            onClick={() => navigate('/onboarding/voice')}
          >
            Skip for now
          </Button>
        </div>

        <p className="text-xs text-text-muted text-center">
          Step 2 of 4 — GitHub verification
        </p>
      </div>
    </div>
  )
}
