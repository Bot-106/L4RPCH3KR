import React, { useState, useCallback } from 'react';
import { View, StyleSheet, Alert, TextInput } from 'react-native';

import { Screen, Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { consumePairingToken, getSession } from '@/services/api';
import { wsClient } from '@/services/ws';
import { useSessionStore } from '@/stores/session';

// react-native-vision-camera is installed but requires native build to function.
// The scan path is available when the camera permission is granted.
// For the simulator, a manual token entry fallback is always shown.

type State = 'idle' | 'scanning' | 'processing' | 'success' | 'error';

export function ScanQrScreen() {
  const { colors, spacing, radius } = useTheme();
  const { setSession } = useSessionStore();

  const [state, setState] = useState<State>('idle');
  const [manualToken, setManualToken] = useState('');

  const handleToken = useCallback(
    async (token: string) => {
      if (!token.trim()) return;
      setState('processing');
      try {
        const { session_id } = await consumePairingToken(token.trim());
        const { session } = await getSession(session_id);
        setSession(session);
        wsClient.subscribeSession(session_id);
        setState('success');
      } catch (e: unknown) {
        setState('error');
        Alert.alert(
          'Scan failed',
          e instanceof Error ? e.message : 'Could not consume token.',
        );
      }
    },
    [setSession],
  );

  return (
    <Screen style={{ gap: spacing[6] }}>
      <View style={{ gap: spacing[2], paddingTop: spacing[4] }}>
        <ThemedText size="2xl" weight="bold">
          Scan partner's QR
        </ThemedText>
        <ThemedText size="md" variant="secondary">
          Ask your conversation partner to show you their QR code, then scan
          it here to start the session and consent to recording.
        </ThemedText>
      </View>

      {/* Camera viewfinder placeholder */}
      <View
        style={[
          styles.viewfinder,
          {
            backgroundColor: colors.bg.surface,
            borderColor: colors.border.default,
            borderRadius: radius.lg,
          },
        ]}
      >
        {state !== 'success' && (
          <>
            <View
              style={[
                styles.scanFrame,
                { borderColor: colors.accent.default },
              ]}
            />
            <ThemedText size="sm" variant="muted" style={{ marginTop: spacing[3] }}>
              Camera requires native build.{'\n'}Use manual entry below.
            </ThemedText>
          </>
        )}
        {state === 'success' && (
          <View style={{ alignItems: 'center', gap: spacing[3] }}>
            <ThemedText size="3xl">✓</ThemedText>
            <ThemedText
              size="lg"
              weight="semibold"
              style={{ color: colors.accent.default }}
            >
              Partner paired!
            </ThemedText>
            <ThemedText size="sm" variant="secondary" style={{ textAlign: 'center' }}>
              Your consent has been registered. Switch to Live.
            </ThemedText>
          </View>
        )}
      </View>

      {state !== 'success' && (
        <View style={{ gap: spacing[3] }}>
          <ThemedText size="sm" variant="secondary">
            Or enter the token manually:
          </ThemedText>
          <TextInput
            style={[
              styles.inputRow,
              {
                backgroundColor: colors.bg.surface,
                borderColor: colors.border.default,
                borderRadius: radius.md,
                padding: spacing[3],
                color: colors.text.primary,
                fontFamily: 'Courier',
                fontSize: 13,
                borderWidth: 1,
              },
            ]}
            value={manualToken}
            onChangeText={setManualToken}
            placeholder="Paste token here"
            placeholderTextColor={colors.text.muted}
            autoCapitalize="none"
            autoCorrect={false}
            onSubmitEditing={() => handleToken(manualToken)}
          />
          <Button
            label={state === 'processing' ? 'Connecting…' : 'Connect with token'}
            loading={state === 'processing'}
            disabled={state === 'processing'}
            onPress={() => handleToken(manualToken)}
          />
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  viewfinder: {
    height: 300,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  scanFrame: {
    width: 200,
    height: 200,
    borderWidth: 2,
    borderRadius: 8,
  },
  inputRow: {
    borderWidth: 1,
    minHeight: 44,
    justifyContent: 'center',
  },
});
