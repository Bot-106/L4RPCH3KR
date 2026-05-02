import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { Button } from '@/components/Button'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { initPiPair } from '@/lib/api'
import { colors } from '@/theme/tokens'

export function PiPairScreen() {
  const navigate = useNavigate()
  const [pairToken, setPairToken] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function fetchPairToken() {
    setError('')
    setLoading(true)
    try {
      const res = await initPiPair()
      setPairToken(res.pair_token)
      setExpiresAt(res.expires_at)
    } catch {
      setError('Could not generate pairing QR. Check your connection.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void fetchPairToken()
  }, [])

  const expired = expiresAt ? new Date(expiresAt) < new Date() : false

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm flex flex-col gap-8">
        <div className="flex flex-col gap-2">
          <div className="w-12 h-12 rounded-full bg-bg-raised flex items-center justify-center mb-2">
            <span className="text-2xl">📡</span>
          </div>
          <h2 className="text-xl font-bold text-text-primary">Pair your Pi</h2>
          <p className="text-sm text-text-secondary">
            Have your Raspberry Pi scan this QR code to link it to your account.
          </p>
        </div>

        <div className="flex flex-col items-center gap-4">
          {loading ? (
            <div className="w-48 h-48 flex items-center justify-center">
              <LoadingSpinner size="lg" />
            </div>
          ) : error ? (
            <p className="text-sm text-severity-high bg-severity-high/10 border border-severity-high/20 rounded-md px-4 py-3 w-full">
              {error}
            </p>
          ) : pairToken ? (
            <>
              <div
                className="p-4 rounded-lg"
                style={{ background: expired ? colors.bg.surface : '#ffffff' }}
              >
                {expired ? (
                  <div className="w-40 h-40 flex items-center justify-center">
                    <p className="text-sm text-text-muted text-center">QR expired</p>
                  </div>
                ) : (
                  <QRCodeSVG
                    value={pairToken}
                    size={160}
                    bgColor="#ffffff"
                    fgColor={colors.bg.canvas}
                  />
                )}
              </div>
              {expiresAt && !expired && (
                <p className="text-xs text-text-muted">
                  Expires {new Date(expiresAt).toLocaleTimeString()}
                </p>
              )}
              {expired && (
                <Button variant="secondary" onClick={fetchPairToken}>
                  Regenerate QR
                </Button>
              )}
            </>
          ) : null}
        </div>

        <div className="flex flex-col gap-3">
          <Button onClick={() => navigate('/live')} fullWidth>
            Done — go to live view
          </Button>
          <Button variant="ghost" fullWidth onClick={fetchPairToken}>
            Regenerate QR
          </Button>
        </div>

        <p className="text-xs text-text-muted text-center">
          Step 4 of 4 — Pi pairing
        </p>
      </div>
    </div>
  )
}
