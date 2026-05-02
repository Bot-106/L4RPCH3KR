// Type shim for @env (react-native-dotenv).
// Matches variables declared in .env / .env.example.
declare module '@env' {
  export const API_BASE: string;
  export const WS_BASE: string;
  export const DEEP_LINK_SCHEME: string;
}
