/**
 * Manages LLM API keys stored in browser cookies.
 * Allows users to provide their own Anthropic or OpenAI keys instead of using server-side keys.
 */

const API_KEY_COOKIE_PREFIX = "larpchekr_llm_";
const COOKIE_MAX_AGE = 30 * 24 * 60 * 60; // 30 days

export type LLMProvider = "anthropic" | "openai";

/**
 * Set an API key in a cookie for a given provider
 */
export function setApiKey(provider: LLMProvider, apiKey: string) {
  if (typeof window === "undefined") return;
  const expires = new Date();
  expires.setSeconds(expires.getSeconds() + COOKIE_MAX_AGE);
  document.cookie = `${API_KEY_COOKIE_PREFIX}${provider}=${encodeURIComponent(apiKey)}; path=/; expires=${expires.toUTCString()}; SameSite=Strict`;
}

/**
 * Get an API key from cookies for a given provider
 */
export function getApiKey(provider: LLMProvider): string | null {
  if (typeof window === "undefined") return null;
  const name = `${API_KEY_COOKIE_PREFIX}${provider}=`;
  const decodedCookie = decodeURIComponent(document.cookie);
  const cookieArray = decodedCookie.split(";");
  for (let cookie of cookieArray) {
    cookie = cookie.trim();
    if (cookie.indexOf(name) === 0) {
      return cookie.substring(name.length);
    }
  }
  return null;
}

/**
 * Check if an API key is configured for a provider
 */
export function hasApiKey(provider: LLMProvider): boolean {
  return getApiKey(provider) !== null;
}

/**
 * Clear an API key from cookies
 */
export function clearApiKey(provider: LLMProvider) {
  if (typeof window === "undefined") return;
  document.cookie = `${API_KEY_COOKIE_PREFIX}${provider}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC; SameSite=Strict`;
}

/**
 * Get all configured API keys
 */
export function getAllApiKeys(): Partial<Record<LLMProvider, string>> {
  const keys: Partial<Record<LLMProvider, string>> = {};
  const anthropic = getApiKey("anthropic");
  const openai = getApiKey("openai");
  if (anthropic) keys.anthropic = anthropic;
  if (openai) keys.openai = openai;
  return keys;
}

/**
 * Send API key to backend header for use in LLM requests
 * This should be passed in headers when making requests that need LLM
 */
export function getApiKeyHeaders(provider: LLMProvider): Record<string, string> {
  const key = getApiKey(provider);
  if (!key) return {};
  return {
    "X-LLM-API-Key": key,
    "X-LLM-Provider": provider
  };
}
