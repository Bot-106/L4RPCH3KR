import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Final values come from ../design/tokens/tokens.json via src/lib/tokens.ts.
      // Until designer ships tokens, src/lib/tokens.ts exposes placeholders that
      // are wired into theme.extend in a future commit.
    }
  },
  plugins: []
};

export default config;
