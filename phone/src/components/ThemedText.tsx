import React from 'react';
import { Text, type TextProps, StyleSheet } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';

interface Props extends TextProps {
  variant?: 'primary' | 'secondary' | 'muted' | 'inverse';
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl';
  weight?: 'regular' | 'medium' | 'semibold' | 'bold';
}

export function ThemedText({
  variant = 'primary',
  size = 'md',
  weight = 'regular',
  style,
  ...props
}: Props) {
  const { colors, fontSize, fontWeight } = useTheme();
  return (
    <Text
      style={[
        {
          color: colors.text[variant],
          fontSize: fontSize[size],
          fontWeight: fontWeight[weight],
        },
        style,
      ]}
      {...props}
    />
  );
}
