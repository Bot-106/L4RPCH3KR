const JWT_KEY = 'jwt'
const USER_KEY = 'user'

export function getJwt(): string | null {
  return localStorage.getItem(JWT_KEY)
}

export function setJwt(token: string): void {
  localStorage.setItem(JWT_KEY, token)
}

export function clearJwt(): void {
  localStorage.removeItem(JWT_KEY)
  localStorage.removeItem(USER_KEY)
}
