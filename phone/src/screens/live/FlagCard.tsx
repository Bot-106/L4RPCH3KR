import React, { useEffect, useCallback } from 'react';
import {
  View,
  StyleSheet,
  TouchableOpacity,
  Dimensions,
} from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withSpring,
  runOnJS,
  Easing,
} from 'react-native-reanimated';
import { useTheme } from '@/theme/ThemeProvider';
import { ThemedText } from '@/components';
import type { ActiveFlag } from '@/stores/session';
import type { Severity } from '@/contracts';

const { width: SCREEN_WIDTH } = Dimensions.get('window');
const CARD_WIDTH = SCREEN_WIDTH - 32;
const AUTO_DISMISS_MS = 8_000;

interface Props {
  activeFlag: ActiveFlag;
  onDismiss: (flagId: string) => void;
  onLock: (flagId: string) => void;
}

export function FlagCard({ activeFlag, onDismiss, onLock }: Props) {
  const { colors, spacing, radius, shadow, motion } = useTheme();
  const { flag, claim, lockedOpen } = activeFlag;

  const translateX = useSharedValue(CARD_WIDTH + 32);
  const opacity = useSharedValue(0);

  const dismiss = useCallback(() => {
    onDismiss(flag.id);
  }, [flag.id, onDismiss]);

  // Slide in on mount
  useEffect(() => {
    translateX.value = withSpring(0, { damping: 18, stiffness: 180 });
    opacity.value = withTiming(1, { duration: motion.duration.fast });
  }, []);

  // Auto-dismiss after 8s unless locked
  useEffect(() => {
    if (lockedOpen) return;
    const timer = setTimeout(() => {
      translateX.value = withTiming(
        CARD_WIDTH + 32,
        { duration: motion.duration.normal, easing: Easing.out(Easing.ease) },
        (finished) => {
          if (finished) runOnJS(dismiss)();
        },
      );
    }, AUTO_DISMISS_MS);
    return () => clearTimeout(timer);
  }, [lockedOpen, motion.duration.normal, translateX, dismiss]);

  const animStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
    opacity: opacity.value,
  }));

  const severityColor = {
    low: colors.severity.low,
    medium: colors.severity.medium,
    high: colors.severity.high,
  }[flag.severity];

  return (
    <Animated.View style={[styles.container, animStyle]}>
      <TouchableOpacity
        activeOpacity={0.9}
        onPress={() => onLock(flag.id)}
        style={[
          styles.card,
          {
            backgroundColor: colors.bg.raised,
            borderRadius: radius.lg,
            borderLeftWidth: 4,
            borderLeftColor: severityColor,
            padding: spacing[4],
            ...shadow.md,
            width: CARD_WIDTH,
          },
        ]}
      >
        <View style={styles.header}>
          <SeverityBadge severity={flag.severity} />
          <TouchableOpacity
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            onPress={dismiss}
          >
            <ThemedText size="sm" variant="muted">✕</ThemedText>
          </TouchableOpacity>
        </View>

        <ThemedText size="md" weight="semibold" style={{ marginTop: spacing[2] }}>
          {claim.text_span}
        </ThemedText>

        <View
          style={[
            styles.rebuttal,
            {
              backgroundColor: colors.bg.surface,
              borderRadius: radius.sm,
              padding: spacing[2],
              marginTop: spacing[2],
            },
          ]}
        >
          <ThemedText size="sm" variant="secondary">
            {flag.verified_text}
          </ThemedText>
        </View>

        {!lockedOpen && (
          <ThemedText size="xs" variant="muted" style={{ marginTop: spacing[2] }}>
            Tap to keep open
          </ThemedText>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
}

function SeverityBadge({ severity }: { severity: Severity }) {
  const { colors, spacing, radius, fontSize } = useTheme();
  const color = {
    low: colors.severity.low,
    medium: colors.severity.medium,
    high: colors.severity.high,
  }[severity];

  const label = { low: 'Low', medium: 'Medium', high: 'High!' }[severity];

  return (
    <View
      style={{
        backgroundColor: color + '22',
        borderRadius: radius.sm,
        paddingHorizontal: spacing[2],
        paddingVertical: 2,
      }}
    >
      <ThemedText
        size="xs"
        weight="semibold"
        style={{ color, fontSize: fontSize.xs }}
      >
        {label}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    bottom: 100,
    right: 16,
  },
  card: {
    borderWidth: 0,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  rebuttal: {},
});
