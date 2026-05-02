// Imports design tokens from the shared design directory.
// When the designer ships tokens.json, swap the import path — no other change needed.
// Metro is configured (watchFolders) to resolve outside the phone/ directory.
// Path: phone/src/theme/tokens.ts → L4RPCH3KR/design/tokens/tokens.example.json
// Metro watchFolders configured in metro.config.js to include ../design
import rawTokens from '../../../design/tokens/tokens.example.json';

type TokenValue<T> = { $value: T; $type: string };

function val<T>(token: TokenValue<T>): T {
  return token.$value;
}

const t = rawTokens;

export const colors = {
  bg: {
    canvas: val(t.color.bg.canvas),
    surface: val(t.color.bg.surface),
    raised: val(t.color.bg.raised),
  },
  text: {
    primary: val(t.color.text.primary),
    secondary: val(t.color.text.secondary),
    muted: val(t.color.text.muted),
    inverse: val(t.color.text.inverse),
  },
  border: {
    default: val(t.color.border.default),
    strong: val(t.color.border.strong),
  },
  accent: {
    default: val(t.color.accent.default),
    strong: val(t.color.accent.strong),
  },
  severity: {
    low: val(t.color.severity.low),
    medium: val(t.color.severity.medium),
    high: val(t.color.severity.high),
  },
  status: {
    recording: val(t.color.status.recording),
    armed: val(t.color.status.armed),
    offline: val(t.color.status.offline),
  },
} as const;

export const fontFamily = {
  sans: 'System',
  mono: 'Courier',
} as const;

export const fontSize = {
  xs: val(t.font.size.xs),
  sm: val(t.font.size.sm),
  md: val(t.font.size.md),
  lg: val(t.font.size.lg),
  xl: val(t.font.size.xl),
  '2xl': val(t.font.size['2xl']),
  '3xl': val(t.font.size['3xl']),
} as const;

export const fontWeight = {
  regular: '400' as const,
  medium: '500' as const,
  semibold: '600' as const,
  bold: '700' as const,
};

export const lineHeight = {
  tight: val(t.font.lineHeight.tight),
  normal: val(t.font.lineHeight.normal),
  relaxed: val(t.font.lineHeight.relaxed),
} as const;

export const spacing = {
  0: val(t.spacing['0']),
  1: val(t.spacing['1']),
  2: val(t.spacing['2']),
  3: val(t.spacing['3']),
  4: val(t.spacing['4']),
  6: val(t.spacing['6']),
  8: val(t.spacing['8']),
  12: val(t.spacing['12']),
  16: val(t.spacing['16']),
  24: val(t.spacing['24']),
} as const;

export const radius = {
  sm: val(t.radius.sm),
  md: val(t.radius.md),
  lg: val(t.radius.lg),
  full: val(t.radius.full),
} as const;

export const shadow = {
  sm: {
    shadowOffset: { width: t.shadow.sm.$value.x, height: t.shadow.sm.$value.y },
    shadowRadius: t.shadow.sm.$value.blur,
    shadowColor: t.shadow.sm.$value.color,
    shadowOpacity: t.shadow.sm.$value.opacity,
    elevation: 2,
  },
  md: {
    shadowOffset: { width: t.shadow.md.$value.x, height: t.shadow.md.$value.y },
    shadowRadius: t.shadow.md.$value.blur,
    shadowColor: t.shadow.md.$value.color,
    shadowOpacity: t.shadow.md.$value.opacity,
    elevation: 6,
  },
  lg: {
    shadowOffset: { width: t.shadow.lg.$value.x, height: t.shadow.lg.$value.y },
    shadowRadius: t.shadow.lg.$value.blur,
    shadowColor: t.shadow.lg.$value.color,
    shadowOpacity: t.shadow.lg.$value.opacity,
    elevation: 12,
  },
} as const;

export const motion = {
  duration: {
    fast: val(t.motion.duration.fast),
    normal: val(t.motion.duration.normal),
    slow: val(t.motion.duration.slow),
  },
} as const;

export const tokens = {
  colors,
  fontFamily,
  fontSize,
  fontWeight,
  lineHeight,
  spacing,
  radius,
  shadow,
  motion,
} as const;

export type Tokens = typeof tokens;
