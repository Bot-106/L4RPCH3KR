import axios from 'axios'
import type { AxiosInstance } from 'axios'
import { getJwt, clearJwt } from './auth'
import type {
  MagicLinkResponse,
  AuthCallbackResponse,
  User,
  VoiceCalibrationResponse,
  PiPairResponse,
  PairingCreateResponse,
  PairingConsumeResponse,
  SessionResponse,
  RecapResponse,
  FlagDisputeResponse,
} from '@/contracts/types'

const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const jwt = getJwt()
  if (jwt) {
    config.headers.Authorization = `Bearer ${jwt}`
  }
  return config
})

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      clearJwt()
      window.location.href = '/onboarding/signin'
    }
    return Promise.reject(err)
  },
)

// Auth

export async function requestMagicLink(email: string): Promise<MagicLinkResponse> {
  const res = await client.post<MagicLinkResponse>('/auth/magic-link', { email })
  return res.data
}

export async function magicLinkCallback(token: string): Promise<AuthCallbackResponse> {
  const res = await client.get<AuthCallbackResponse>(`/auth/magic-link/callback?token=${token}`)
  return res.data
}

export async function getGithubStartUrl(redirect: string): Promise<string> {
  const res = await client.get<{ url: string }>(`/auth/github/start?redirect=${encodeURIComponent(redirect)}`)
  return res.data.url
}

// Users

export async function getMe(): Promise<User> {
  const res = await client.get<User>('/users/me')
  return res.data
}

export async function uploadVoiceCalibration(blob: Blob): Promise<VoiceCalibrationResponse> {
  const form = new FormData()
  form.append('audio', blob, 'calibration.webm')
  const res = await client.post<VoiceCalibrationResponse>('/users/me/voice-calibration', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function initPiPair(): Promise<PiPairResponse> {
  const res = await client.post<PiPairResponse>('/users/me/pi-pair', {})
  return res.data
}

// Pairings (partner identification)

export async function createPairing(): Promise<PairingCreateResponse> {
  const res = await client.post<PairingCreateResponse>('/pairings')
  return res.data
}

export async function consumePairing(token: string): Promise<PairingConsumeResponse> {
  const res = await client.post<PairingConsumeResponse>('/pairings/consume', { token })
  return res.data
}

// Sessions

export async function getSession(id: string): Promise<SessionResponse> {
  const res = await client.get<SessionResponse>(`/sessions/${id}`)
  return res.data
}

export async function getSessionRecap(id: string): Promise<RecapResponse> {
  const res = await client.get<RecapResponse>(`/sessions/${id}/recap`)
  return res.data
}

// Flags

export async function disputeFlag(id: string, reason: string): Promise<FlagDisputeResponse> {
  const res = await client.post<FlagDisputeResponse>(`/flags/${id}/dispute`, { reason })
  return res.data
}

export { client }
