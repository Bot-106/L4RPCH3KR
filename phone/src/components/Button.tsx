import React from 'react';
import {
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  type TouchableOpacityProps,
} from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { ThemedText } from './ThemedText';

interface Props extends TouchableOpacityProps {
  label: string;
  variant?: 'primary' | 'ghost';
  loading?: boolean;
}

export function Button({
  label,
  variant = 'primary',
  loading = false,
  disabled,
  style,
  ...props
}: Props) {
  const { colors, spacing, radius, fontSize, fontWeight } = useTheme();

  const isPrimary = variant === 'primary';
  const isDisabled = disabled || loading;

  return (
    <TouchableOpacity
      activeOpacity={0.75}
      disabled={isDisabled}
      style={[
        styles.base,
        {
          backgroundColor: isPrimary ? colors.accent.default : 'transparent',
          borderColor: isPrimary ? 'transparent' : colors.border.strong,
          borderWidth: isPrimary ? 0 : 1,
          paddingVertical: spacing[3],
          paddingHorizontal: spacing[6],
          borderRadius: radius.md,
          opacity: isDisabled ? 0.5 : 1,
        },
        style,
      ]}
      {...props}
    >
      {loading ? (
        <ActivityIndicator
          color={isPrimary ? colors.text.inverse : colors.text.primary}
          size="small"
        />
      ) : (
        <ThemedText
          variant={isPrimary ? 'inverse' : 'primary'}
          size="md"
          weight="semibold"
          style={{ textAlign: 'center' }}
        >
          {label}
        </ThemedText>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  base: {
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
  },
});
