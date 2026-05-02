import React, { useState } from 'react';
import {
  View,
  TextInput,
  StyleSheet,
  Modal,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';

import { Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { disputeFlag } from '@/services/api';

interface Props {
  flagId: string;
  visible: boolean;
  onClose: () => void;
  onSuccess: (flagId: string, reason: string) => void;
}

export function DisputeSheet({ flagId, visible, onClose, onSuccess }: Props) {
  const { colors, spacing, radius, fontSize } = useTheme();
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    if (!reason.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await disputeFlag(flagId, reason.trim());
      onSuccess(flagId, reason.trim());
      setReason('');
      onClose();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Could not submit dispute.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={onClose}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.overlay}
      >
        <TouchableOpacity style={styles.backdrop} activeOpacity={1} onPress={onClose} />

        <View
          style={[
            styles.sheet,
            {
              backgroundColor: colors.bg.raised,
              borderTopLeftRadius: radius.lg,
              borderTopRightRadius: radius.lg,
              padding: spacing[6],
              gap: spacing[4],
            },
          ]}
        >
          <ThemedText size="xl" weight="semibold">
            Dispute this flag
          </ThemedText>
          <ThemedText size="sm" variant="secondary">
            Briefly explain why this flag is inaccurate. The organizer will
            review it.
          </ThemedText>

          <TextInput
            style={[
              styles.input,
              {
                backgroundColor: colors.bg.surface,
                borderColor: colors.border.default,
                borderRadius: radius.md,
                color: colors.text.primary,
                fontSize: fontSize.md,
                padding: spacing[3],
              },
            ]}
            placeholder="E.g. I do have Rust experience, just on a private repo"
            placeholderTextColor={colors.text.muted}
            multiline
            numberOfLines={4}
            value={reason}
            onChangeText={setReason}
            textAlignVertical="top"
          />

          {error && (
            <ThemedText size="sm" style={{ color: colors.severity.high }}>
              {error}
            </ThemedText>
          )}

          <Button
            label="Submit dispute"
            onPress={handleSubmit}
            loading={loading}
            disabled={!reason.trim()}
          />
          <Button label="Cancel" variant="ghost" onPress={onClose} disabled={loading} />
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: 'flex-end',
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.5)',
  },
  sheet: {},
  input: {
    borderWidth: 1,
    minHeight: 100,
  },
});
