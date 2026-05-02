import React, { createContext, useContext } from 'react';
import { tokens, type Tokens } from './tokens';

const ThemeContext = createContext<Tokens>(tokens);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ThemeContext.Provider value={tokens}>{children}</ThemeContext.Provider>
  );
}

export function useTheme(): Tokens {
  return useContext(ThemeContext);
}
