import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { Screen, Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { initPiPair } from '@/services/api';
import { wsClient } from '@/services/ws';
import { useAuthStore } from '@/stores/auth';
import type { OnboardingStackParamList } from '@/navigation/RootNavigator';
import { isExpired } from '@/lib/time';

type State = 'loading' | 'showing_qr' | 'paired' | 'error';

type Props = NativeStackScreenProps<OnboardingStackParamList, 'PiPair'>;

export function PiPairScreen({ navigation }: Props) {
  const { colors, spacing, radius } = useTheme();
  const { user, jwt } = useAuthStore();

  const [state, setState] = useState<State>('loading');
  const [pairToken, setPairToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);

  const fetchPairToken = useCallback(async () => {
    setState('loading');
    try {
      const { pair_token, expires_at } = await initPiPair();
      setPairToken(pair_token);
      setExpiresAt(expires_at);
      setState('showing_qr');
    } catch (e: unknown) {
      setState('error');
      Alert.alert('Error', e instanceof Error ? e.message : 'Could not generate pairing QR.');
    }
  }, []);

  useEffect(() => {
    fetchPairToken();
  }, [fetchPairToken]);

  // Auto-refresh token before it expires
  useEffect(() => {
    if (!expiresAt) return;
    const ms = new Date(expiresAt).getTime() - Date.now() - 5000;
    if (ms <= 0) {
      fetchPairToken();
      return;
    }
    const timer = setTimeout(fetchPairToken, ms);
    return () => clearTimeout(timer);
  }, [expiresAt, fetchPairToken]);

  // Listen for Pi pair confirmation over WS.
  // The backend emits session_status with status=armed once the Pi claims the token.
  useEffect(() => {
    if (!jwt || !user) return;
    wsClient.setCredentials(jwt, user.id);
    wsClient.connect();

    const off = wsClient.on('session_status', (data) => {
      if (data.status === 'armed' || data.status === 'active') {
        setState('paired');
      }
    });
    return () => {
      off();
    };
  }, [jwt, user]);

  function handleContinueToLive() {
    // RootNavigator re-renders when user.voice_calibration_id is set, switching
    // automatically to the Main tabs. This is a no-op navigation call that lets
    // the auth state drive routing rather than pushing manually.
    navigation.getParent()?.goBack();
  }

  return (
    <Screen style={{ justifyContent: 'center', gap: spacing[6] }}>
      <View style={{ gap: spacing[2] }}>
        <ThemedText size="2xl" weight="bold">
          Pair your Pi
        </ThemedText>
        <ThemedText size="md" variant="secondary">
          Have your Pi scan the QR code below. Once it connects, you're ready
          for live mode.
        </ThemedText>
      </View>

      <View
        style={[
          styles.qrContainer,
          {
            backgroundColor: colors.bg.surface,
            borderColor: colors.border.default,
            borderRadius: radius.lg,
            padding: spacing[6],
          },
        ]}
      >
        {state === 'loading' && (
          <ActivityIndicator color={colors.accent.default} size="large" />
        )}

        {state === 'showing_qr' && pairToken && (
          <View style={{ alignItems: 'center', gap: spacing[4] }}>
            {/* QR placeholder — replace with react-native-qrcode-svg once available */}
            <View
              style={[
                styles.qrPlaceholder,
                {
                  backgroundColor: colors.bg.raised,
                  borderRadius: radius.md,
                  borderWidth: 1,
                  borderColor: colors.border.strong,
                },
              ]}
            >
              <ThemedText size="xs" variant="muted" style={{ textAlign: 'center' }}>
                QR placeholder{'\n'}(install react-native-qrcode-svg)
              </ThemedText>
              <ThemedText
                size="sm"
                style={{ textAlign: 'center', fontFamily: 'Courier', marginTop: 8 }}
                variant="secondary"
              >
                {pairToken}
              </ThemedText>
            </View>
            <ThemedText size="xs" variant="muted">
              Token expires in ~60s — auto-refreshes
            </ThemedText>
          </View>
        )}

        {state === 'paired' && (
          <View style={{ alignItems: 'center', gap: spacing[3] }}>
            <ThemedText size="3xl">✓</ThemedText>
            <ThemedText size="lg" weight="semibold" style={{ color: colors.accent.default }}>
              Pi paired!
            </ThemedText>
          </View>
        )}

        {state === 'error' && (
          <ThemedText size="sm" variant="secondary" style={{ textAlign: 'center' }}>
            Could not generate QR. Check your connection and try again.
          </ThemedText>
        )}
      </View>

      <View style={{ gap: spacing[3] }}>
        {state === 'paired' && (
          <Button label="Enter live mode" onPress={handleContinueToLive} />
        )}
        {state === 'error' && (
          <Button label="Retry" onPress={fetchPairToken} />
        )}
        {(state === 'loading' || state === 'showing_qr') && (
          <Button
            label="Skip for now"
            variant="ghost"
            onPress={handleContinueToLive}
          />
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  qrContainer: {
    borderWidth: 1,
    alignItems: 'center',
    minHeight: 240,
    justifyContent: 'center',
  },
  qrPlaceholder: {
    width: 200,
    height: 200,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
  },
});
