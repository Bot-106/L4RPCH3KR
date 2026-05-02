import React from 'react';
import { View, StyleSheet, type ViewProps } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useTheme } from '@/theme/ThemeProvider';

interface Props extends ViewProps {
  safe?: boolean;
  padded?: boolean;
}

export function Screen({ safe = true, padded = true, style, children, ...props }: Props) {
  const { colors, spacing } = useTheme();

  const inner = (
    <View
      style={[
        styles.fill,
        { backgroundColor: colors.bg.canvas },
        padded && { padding: spacing[4] },
        style,
      ]}
      {...props}
    >
      {children}
    </View>
  );

  if (safe) {
    return (
      <SafeAreaView style={[styles.fill, { backgroundColor: colors.bg.canvas }]}>
        {inner}
      </SafeAreaView>
    );
  }

  return inner;
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
});
