import React from 'react';
import { View, StyleSheet } from 'react-native';
import { useTheme } from '@/theme/ThemeProvider';
import { ThemedText } from '@/components';
import type { SessionStatusValue } from '@/contracts';

type WsStatus = 'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'paused';

interface Props {
  sessionStatus: SessionStatusValue | null;
  wsStatus: WsStatus;
}

interface PillConfig {
  label: string;
  color: string;
  dotColor: string;
}

export function StatusPill({ sessionStatus, wsStatus }: Props) {
  const { colors, spacing, radius } = useTheme();

  const config = resolveConfig(sessionStatus, wsStatus, colors);

  return (
    <View
      style={[
        styles.pill,
        {
          backgroundColor: colors.bg.raised,
          borderColor: config.color,
          borderRadius: radius.full,
          paddingHorizontal: spacing[3],
          paddingVertical: spacing[1],
        },
      ]}
    >
      <View
        style={[
          styles.dot,
          { backgroundColor: config.dotColor },
        ]}
      />
      <ThemedText size="sm" weight="medium" style={{ color: config.color }}>
        {config.label}
      </ThemedText>
    </View>
  );
}

function resolveConfig(
  sessionStatus: SessionStatusValue | null,
  wsStatus: WsStatus,
  colors: ReturnType<typeof useTheme>['colors'],
): PillConfig {
  if (wsStatus === 'paused') {
    return { label: 'Paused', color: colors.status.offline, dotColor: colors.status.offline };
  }
  if (wsStatus === 'disconnected' || wsStatus === 'reconnecting') {
    return { label: 'Disconnected', color: colors.status.offline, dotColor: colors.status.offline };
  }
  if (wsStatus === 'connecting') {
    return { label: 'Connecting…', color: colors.status.armed, dotColor: colors.status.armed };
  }
  // Connected — use session status
  switch (sessionStatus) {
    case 'active':
      return { label: 'Recording', color: colors.status.recording, dotColor: colors.status.recording };
    case 'armed':
      return { label: 'Armed', color: colors.status.armed, dotColor: colors.status.armed };
    case 'ended':
      return { label: 'Session ended', color: colors.text.muted, dotColor: colors.text.muted };
    default:
      return { label: 'Connected', color: colors.accent.default, dotColor: colors.accent.default };
  }
}

const styles = StyleSheet.create({
  pill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    alignSelf: 'center',
    borderWidth: 1,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 999,
  },
});
