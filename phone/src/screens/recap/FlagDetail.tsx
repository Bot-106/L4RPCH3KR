import React, { useState } from 'react';
import { View, StyleSheet, TouchableOpacity, Alert } from 'react-native';

import { ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { DisputeSheet } from './DisputeSheet';
import type { Flag, Claim, Utterance } from '@/contracts';
import { formatTimestamp } from '@/lib/time';

interface Props {
  flag: Flag;
  claim: Claim;
  utterance: Utterance;
  audioUrl: string | null;
  onDisputeSuccess: (flagId: string, reason: string) => void;
}

export function FlagDetail({ flag, claim, utterance, audioUrl, onDisputeSuccess }: Props) {
  const { colors, spacing, radius } = useTheme();
  const [expanded, setExpanded] = useState(false);
  const [disputeOpen, setDisputeOpen] = useState(false);

  const severityColor = {
    low: colors.severity.low,
    medium: colors.severity.medium,
    high: colors.severity.high,
  }[flag.severity];

  function handlePlayAudio() {
    // Full implementation: use expo-av or react-native-sound to play audioUrl.
    Alert.alert('Audio playback', audioUrl ? `Playing: ${audioUrl}` : 'No audio available.');
  }

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: colors.bg.surface,
          borderRadius: radius.md,
          borderLeftWidth: 4,
          borderLeftColor: severityColor,
          marginBottom: spacing[3],
          overflow: 'hidden',
        },
      ]}
    >
      <TouchableOpacity
        onPress={() => setExpanded((e) => !e)}
        activeOpacity={0.8}
        style={{ padding: spacing[4] }}
      >
        <View style={styles.row}>
          <View
            style={[
              styles.badge,
              {
                backgroundColor: severityColor + '22',
                borderRadius: radius.sm,
                paddingHorizontal: spacing[2],
                paddingVertical: 2,
              },
            ]}
          >
            <ThemedText size="xs" weight="semibold" style={{ color: severityColor }}>
              {flag.severity.toUpperCase()}
            </ThemedText>
          </View>
          <ThemedText size="xs" variant="muted">
            {formatTimestamp(flag.created_at)}
          </ThemedText>
        </View>

        <ThemedText size="md" weight="medium" style={{ marginTop: spacing[2] }}>
          "{claim.text_span}"
        </ThemedText>
        <ThemedText size="sm" variant="secondary" style={{ marginTop: spacing[1] }}>
          {flag.verified_text}
        </ThemedText>
      </TouchableOpacity>

      {expanded && (
        <View
          style={[
            styles.expanded,
            {
              borderTopColor: colors.border.default,
              borderTopWidth: StyleSheet.hairlineWidth,
              padding: spacing[4],
              gap: spacing[3],
            },
          ]}
        >
          <ThemedText size="sm" variant="secondary">
            Full utterance:
          </ThemedText>
          <View
            style={[
              styles.utteranceBox,
              {
                backgroundColor: colors.bg.raised,
                borderRadius: radius.sm,
                padding: spacing[3],
              },
            ]}
          >
            <ThemedText size="sm">{utterance.text}</ThemedText>
          </View>

          <View style={styles.meta}>
            <ThemedText size="xs" variant="muted">
              Claim kind: {claim.kind.replace(/_/g, ' ')}
            </ThemedText>
            <ThemedText size="xs" variant="muted">
              Confidence: {Math.round(flag.confidence * 100)}%
            </ThemedText>
            {claim.hedge !== 'none' && (
              <ThemedText size="xs" variant="muted">
                Hedge: {claim.hedge}
              </ThemedText>
            )}
          </View>

          <View style={styles.actions}>
            {audioUrl && (
              <TouchableOpacity
                onPress={handlePlayAudio}
                style={[
                  styles.actionBtn,
                  {
                    backgroundColor: colors.bg.canvas,
                    borderColor: colors.border.strong,
                    borderRadius: radius.sm,
                    padding: spacing[2],
                    flex: 1,
                  },
                ]}
              >
                <ThemedText size="sm" style={{ textAlign: 'center' }}>
                  ▶ Play audio
                </ThemedText>
              </TouchableOpacity>
            )}

            {!flag.disputed ? (
              <TouchableOpacity
                onPress={() => setDisputeOpen(true)}
                style={[
                  styles.actionBtn,
                  {
                    backgroundColor: colors.bg.canvas,
                    borderColor: colors.border.strong,
                    borderRadius: radius.sm,
                    padding: spacing[2],
                    flex: 1,
                  },
                ]}
              >
                <ThemedText size="sm" style={{ textAlign: 'center' }}>
                  Dispute
                </ThemedText>
              </TouchableOpacity>
            ) : (
              <View style={{ flex: 1, alignItems: 'center' }}>
                <ThemedText size="sm" variant="muted">
                  Disputed ✓
                </ThemedText>
              </View>
            )}
          </View>
        </View>
      )}

      <DisputeSheet
        flagId={flag.id}
        visible={disputeOpen}
        onClose={() => setDisputeOpen(false)}
        onSuccess={onDisputeSuccess}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {},
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  badge: {},
  expanded: {},
  utteranceBox: {},
  meta: { gap: 4 },
  actions: {
    flexDirection: 'row',
    gap: 8,
  },
  actionBtn: {
    borderWidth: 1,
  },
});
