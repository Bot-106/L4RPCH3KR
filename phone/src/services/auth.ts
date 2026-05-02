import * as SecureStore from 'expo-secure-store';

const JWT_KEY = 'larpchekr.jwt';

export async function loadJwt(): Promise<string | null> {
  try {
    return await SecureStore.getItemAsync(JWT_KEY);
  } catch {
    return null;
  }
}

export async function saveJwt(jwt: string): Promise<void> {
  await SecureStore.setItemAsync(JWT_KEY, jwt);
}

export async function clearJwt(): Promise<void> {
  await SecureStore.deleteItemAsync(JWT_KEY);
}
