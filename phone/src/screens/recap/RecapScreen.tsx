import React, { useCallback } from 'react';
import { View, StyleSheet, FlatList, ActivityIndicator, RefreshControl } from 'react-native';
import { useQuery } from '@tanstack/react-query';

import { Screen, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { FlagDetail } from './FlagDetail';
import { getRecap } from '@/services/api';
import { useSessionStore } from '@/stores/session';
import { formatDuration } from '@/lib/time';
import type { Flag, Claim, Utterance, RecapResponse } from '@/contracts';

export function RecapScreen() {
  const { colors, spacing } = useTheme();
  const session = useSessionStore((s) => s.session);

  const sessionId = session?.id;

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery<RecapResponse, Error>({
    queryKey: ['recap', sessionId],
    queryFn: () => {
      if (!sessionId) throw new Error('No active session');
      return getRecap(sessionId);
    },
    enabled: !!sessionId,
    staleTime: 60_000,
  });

  const handleDisputeSuccess = useCallback(
    (_flagId: string, _reason: string) => {
      refetch();
    },
    [refetch],
  );

  if (!sessionId) {
    return (
      <Screen style={styles.center}>
        <ThemedText size="md" variant="secondary" style={{ textAlign: 'center' }}>
          No session to recap.{'\n'}Start a live session first.
        </ThemedText>
      </Screen>
    );
  }

  if (isLoading) {
    return (
      <Screen style={styles.center}>
        <ActivityIndicator color={colors.accent.default} />
      </Screen>
    );
  }

  if (isError || !data) {
    return (
      <Screen style={styles.center}>
        <ThemedText size="md" variant="secondary" style={{ textAlign: 'center' }}>
          {error?.message ?? 'Could not load recap.'}
        </ThemedText>
      </Screen>
    );
  }

  const { session: sessionData, partner, flags, claims, utterances, score } = data;

  function claimForFlag(flag: Flag): Claim {
    return claims.find((c) => c.id === flag.claim_id) ?? ({} as Claim);
  }

  function utteranceForFlag(flag: Flag): Utterance {
    const claim = claimForFlag(flag);
    return utterances.find((u) => u.id === claim.utterance_id) ?? ({} as Utterance);
  }

  const scoreColor =
    score > 0.6
      ? colors.severity.high
      : score > 0.3
        ? colors.severity.medium
        : colors.severity.low;

  return (
    <FlatList
      style={{ flex: 1, backgroundColor: colors.bg.canvas }}
      contentContainerStyle={{ padding: spacing[4], gap: spacing[4] }}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.accent.default}
        />
      }
      ListHeaderComponent={
        <View style={{ gap: spacing[4] }}>
          {/* Summary card */}
          <View
            style={[
              styles.summaryCard,
              {
                backgroundColor: colors.bg.surface,
                borderRadius: 12,
                padding: spacing[4],
                borderColor: colors.border.default,
                borderWidth: 1,
              },
            ]}
          >
            <ThemedText size="xl" weight="bold" style={{ marginBottom: spacing[3] }}>
              Session recap
            </ThemedText>

            <View style={styles.statRow}>
              <Stat label="Duration" value={formatDuration(sessionData.started_at, sessionData.ended_at)} />
              <Stat label="Flags" value={String(flags.length)} />
              <Stat
                label="Larp score"
                value={`${Math.round(score * 100)}%`}
                valueColor={scoreColor}
              />
            </View>

            {partner && (
              <ThemedText size="sm" variant="secondary" style={{ marginTop: spacing[3] }}>
                Conversation with {partner.full_name}
                {partner.headline ? ` · ${partner.headline}` : ''}
              </ThemedText>
            )}
          </View>

          {flags.length > 0 && (
            <ThemedText size="lg" weight="semibold">
              {flags.length} flag{flags.length !== 1 ? 's' : ''} raised
            </ThemedText>
          )}
        </View>
      }
      ListEmptyComponent={
        <ThemedText size="md" variant="secondary" style={{ textAlign: 'center', paddingVertical: 32 }}>
          No flags were raised during this session.
        </ThemedText>
      }
      data={flags}
      keyExtractor={(flag) => flag.id}
      renderItem={({ item: flag }) => (
        <FlagDetail
          flag={flag}
          claim={claimForFlag(flag)}
          utterance={utteranceForFlag(flag)}
          audioUrl={utteranceForFlag(flag).audio_url ?? null}
          onDisputeSuccess={handleDisputeSuccess}
        />
      )}
    />
  );
}

function Stat({
  label,
  value,
  valueColor,
}: {
  label: string;
  value: string;
  valueColor?: string;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.stat}>
      <ThemedText size="xs" variant="muted">
        {label}
      </ThemedText>
      <ThemedText
        size="xl"
        weight="bold"
        style={valueColor ? { color: valueColor } : undefined}
      >
        {value}
      </ThemedText>
    </View>
  );
}

const styles = StyleSheet.create({
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  summaryCard: {},
  statRow: {
    flexDirection: 'row',
    gap: 24,
  },
  stat: {
    gap: 2,
  },
});
