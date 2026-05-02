import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { QRCodeSVG } from 'qrcode.react'
import { Button } from '@/components/Button'
import { LoadingSpinner } from '@/components/LoadingSpinner'
import { createPairing } from '@/lib/api'
import { colors } from '@/theme/tokens'

export function ShowQrScreen() {
  const navigate = useNavigate()
  const [token, setToken] = useState<string | null>(null)
  const [qrUrl, setQrUrl] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const fetchPairing = useCallback(async () => {
    setError('')
    setLoading(true)
    try {
      const res = await createPairing()
      setToken(res.token)
      setQrUrl(res.qr_url)
      setExpiresAt(res.expires_at)
    } catch {
      setError('Could not generate QR code. Check your connection.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchPairing()
  }, [fetchPairing])

  const expired = expiresAt ? new Date(expiresAt) < new Date() : false
  const qrValue = qrUrl ?? token ?? ''

  return (
    <div className="min-h-screen bg-bg-canvas flex flex-col">
      <div className="flex items-center gap-3 px-6 pt-safe-top pt-6 pb-4 border-b border-border-default">
        <button
          onClick={() => navigate(-1)}
          className="text-text-secondary hover:text-text-primary transition-colors"
        >
          ←
        </button>
        <h2 className="text-lg font-bold text-text-primary">Show QR</h2>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center px-6 gap-6">
        <p className="text-sm text-text-secondary text-center max-w-xs">
          Have your partner scan this code to link the session.
        </p>

        {loading ? (
          <div className="w-48 h-48 flex items-center justify-center">
            <LoadingSpinner size="lg" />
          </div>
        ) : error ? (
          <p className="text-sm text-severity-high bg-severity-high/10 border border-severity-high/20 rounded-md px-4 py-3 w-full max-w-sm text-center">
            {error}
          </p>
        ) : qrValue ? (
          <>
            <div
              className="p-5 rounded-lg"
              style={{ background: expired ? colors.bg.surface : '#ffffff' }}
            >
              {expired ? (
                <div className="w-48 h-48 flex items-center justify-center">
                  <p className="text-sm text-text-muted">Expired</p>
                </div>
              ) : (
                <QRCodeSVG
                  value={qrValue}
                  size={192}
                  bgColor="#ffffff"
                  fgColor={colors.bg.canvas}
                  level="M"
                />
              )}
            </div>
            {expiresAt && !expired && (
              <p className="text-xs text-text-muted">
                Expires at {new Date(expiresAt).toLocaleTimeString()}
              </p>
            )}
          </>
        ) : null}

        <div className="flex flex-col gap-3 w-full max-w-sm">
          <Button onClick={fetchPairing} loading={loading} fullWidth>
            Regenerate
          </Button>
          <Button variant="ghost" onClick={() => navigate('/pair/scan')} fullWidth>
            Scan partner instead
          </Button>
        </div>
      </div>
    </div>
  )
}
