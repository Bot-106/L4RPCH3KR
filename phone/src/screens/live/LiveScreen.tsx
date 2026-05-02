import React, { useEffect, useCallback } from 'react';
import { View, StyleSheet, ScrollView } from 'react-native';

import { ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { StatusPill } from './StatusPill';
import { FlagCard } from './FlagCard';
import { wsClient } from '@/services/ws';
import { useAuthStore } from '@/stores/auth';
import { useSessionStore } from '@/stores/session';
import { triggerFlagHaptic } from '@/lib/haptics';
import { formatDuration } from '@/lib/time';

export function LiveScreen() {
  const { colors, spacing } = useTheme();
  const { user, jwt } = useAuthStore();
  const {
    session,
    sessionStatus,
    partner,
    larpScore,
    activeFlags,
    wsStatus,
    setSessionStatus,
    setPartner,
    setLarpScore,
    pushFlag,
    dismissFlag,
    lockFlag,
    setWsStatus,
  } = useSessionStore();

  // Connect WS and wire events
  useEffect(() => {
    if (!jwt || !user) return;

    wsClient.setCredentials(jwt, user.id);
    setWsStatus('connecting');
    wsClient.connect();

    const offConnected = wsClient.on('_connected', () => setWsStatus('connected'));
    const offDisconnected = wsClient.on('_disconnected', () =>
      setWsStatus('disconnected'),
    );
    const offReconnecting = wsClient.on('_reconnecting', () =>
      setWsStatus('reconnecting'),
    );

    const offStatus = wsClient.on('session_status', (data) => {
      setSessionStatus(data.status, data.partner ?? null);
      if (data.partner) setPartner(data.partner);
    });

    const offPartner = wsClient.on('partner_identified', (data) => {
      setPartner(data.attendee);
    });

    const offFlag = wsClient.on('flag_raised', async (data) => {
      pushFlag(data.flag, data.claim, data.utterance);
      await triggerFlagHaptic(data.flag.severity);
    });

    const offScore = wsClient.on('score_update', (data) => {
      setLarpScore(data.score);
    });

    return () => {
      offConnected();
      offDisconnected();
      offReconnecting();
      offStatus();
      offPartner();
      offFlag();
      offScore();
      wsClient.disconnect();
      setWsStatus('disconnected');
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jwt, user?.id]);

  const handleDismissFlag = useCallback(
    (flagId: string) => dismissFlag(flagId),
    [dismissFlag],
  );
  const handleLockFlag = useCallback(
    (flagId: string) => lockFlag(flagId),
    [lockFlag],
  );

  const isPaused = wsClient.isPaused;

  return (
    <View style={[styles.fill, { backgroundColor: colors.bg.canvas }]}>
      {/* Header */}
      <View
        style={[
          styles.header,
          {
            borderBottomColor: colors.border.default,
            paddingTop: 56,
            paddingHorizontal: spacing[4],
            paddingBottom: spacing[3],
          },
        ]}
      >
        <ThemedText size="lg" weight="semibold">
          Live
        </ThemedText>
        <StatusPill
          sessionStatus={sessionStatus}
          wsStatus={isPaused ? 'paused' : wsStatus}
        />
      </View>

      {/* Body */}
      <ScrollView
        style={styles.fill}
        contentContainerStyle={[styles.body, { padding: spacing[4] }]}
      >
        {session && (
          <View
            style={[
              styles.sessionCard,
              {
                backgroundColor: colors.bg.surface,
                borderRadius: 12,
                padding: spacing[4],
                marginBottom: spacing[4],
                borderColor: colors.border.default,
                borderWidth: 1,
              },
            ]}
          >
            <ThemedText size="sm" variant="secondary">
              Session duration
            </ThemedText>
            <ThemedText size="2xl" weight="bold">
              {formatDuration(session.started_at)}
            </ThemedText>
            {partner && (
              <ThemedText size="sm" variant="secondary" style={{ marginTop: 4 }}>
                Talking with {partner.full_name}
              </ThemedText>
            )}
          </View>
        )}

        {larpScore > 0 && (
          <View
            style={[
              styles.scoreCard,
              {
                backgroundColor: colors.bg.surface,
                borderRadius: 12,
                padding: spacing[4],
                borderColor: colors.border.default,
                borderWidth: 1,
              },
            ]}
          >
            <ThemedText size="sm" variant="secondary">
              Larp score
            </ThemedText>
            <ThemedText
              size="2xl"
              weight="bold"
              style={{ color: larpScoreColor(larpScore, colors) }}
            >
              {Math.round(larpScore * 100)}%
            </ThemedText>
          </View>
        )}

        {!session && wsStatus === 'connected' && (
          <View style={styles.emptyState}>
            <ThemedText size="md" variant="secondary" style={{ textAlign: 'center' }}>
              Waiting for a session to start.{'\n'}
              Make sure your Pi is paired and running.
            </ThemedText>
          </View>
        )}

        {wsStatus === 'paused' && (
          <View
            style={[
              styles.pausedBanner,
              {
                backgroundColor: colors.bg.surface,
                borderRadius: 12,
                padding: spacing[4],
                borderColor: colors.status.offline,
                borderWidth: 1,
              },
            ]}
          >
            <ThemedText size="md" weight="semibold" style={{ color: colors.status.offline }}>
              Live mode paused
            </ThemedText>
            <ThemedText size="sm" variant="secondary">
              Return to the app to resume. Your Pi continues recording.
            </ThemedText>
          </View>
        )}
      </ScrollView>

      {/* Flag cards overlay */}
      {activeFlags.map((af) => (
        <FlagCard
          key={af.flag.id}
          activeFlag={af}
          onDismiss={handleDismissFlag}
          onLock={handleLockFlag}
        />
      ))}
    </View>
  );
}

function larpScoreColor(
  score: number,
  colors: ReturnType<typeof useTheme>['colors'],
): string {
  if (score > 0.6) return colors.severity.high;
  if (score > 0.3) return colors.severity.medium;
  return colors.severity.low;
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  body: {
    flexGrow: 1,
  },
  sessionCard: {},
  scoreCard: {},
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 64,
  },
  pausedBanner: {},
});
