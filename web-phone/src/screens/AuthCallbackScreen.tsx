import { useEffect, useRef } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { magicLinkCallback } from '@/lib/api'
import { useAuthStore } from '@/stores/authStore'

export function AuthCallbackScreen() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const setAuth = useAuthStore((s) => s.setAuth)
  const calledRef = useRef(false)

  useEffect(() => {
    if (calledRef.current) return
    calledRef.current = true

    const token = params.get('token')
    if (!token) {
      navigate('/onboarding/signin', { replace: true })
      return
    }

    async function finalize() {
      try {
        const res = await magicLinkCallback(token!)
        setAuth(res.user, res.jwt)

        // Route to first incomplete onboarding step
        if (!res.user.github_login) {
          navigate('/onboarding/github', { replace: true })
        } else {
          navigate('/live', { replace: true })
        }
      } catch {
        navigate('/onboarding/signin', { replace: true })
      }
    }

    void finalize()
  }, [params, navigate, setAuth])

  return (
    <div className="min-h-screen bg-bg-canvas flex items-center justify-center">
      <LoadingSpinner size="lg" />
    </div>
  )
}
