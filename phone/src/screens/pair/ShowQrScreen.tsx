import React, { useState, useEffect, useCallback } from 'react';
import { View, StyleSheet, ActivityIndicator, Alert } from 'react-native';

import { Screen, Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { createPairingToken } from '@/services/api';
import { wsClient } from '@/services/ws';
import { isExpired } from '@/lib/time';

type State = 'loading' | 'showing' | 'consumed' | 'error';

export function ShowQrScreen() {
  const { colors, spacing, radius } = useTheme();

  const [state, setState] = useState<State>('loading');
  const [token, setToken] = useState<string | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);

  const fetchToken = useCallback(async () => {
    setState('loading');
    try {
      const res = await createPairingToken();
      setToken(res.token);
      setQrUrl(res.qr_url);
      setExpiresAt(res.expires_at);
      setState('showing');
    } catch (e: unknown) {
      setState('error');
      Alert.alert('Error', e instanceof Error ? e.message : 'Could not generate QR.');
    }
  }, []);

  useEffect(() => {
    fetchToken();
  }, [fetchToken]);

  // Auto-refresh token ~5s before expiry
  useEffect(() => {
    if (!expiresAt || state !== 'showing') return;
    const ms = new Date(expiresAt).getTime() - Date.now() - 5000;
    if (ms <= 0) { fetchToken(); return; }
    const timer = setTimeout(fetchToken, ms);
    return () => clearTimeout(timer);
  }, [expiresAt, state, fetchToken]);

  // Listen for partner consuming QR over WS
  useEffect(() => {
    const off = wsClient.on('session_status', (data) => {
      if (data.partner) setState('consumed');
    });
    return off;
  }, []);

  return (
    <Screen style={{ justifyContent: 'center', gap: spacing[6] }}>
      <View style={{ gap: spacing[2] }}>
        <ThemedText size="2xl" weight="bold">
          Your QR
        </ThemedText>
        <ThemedText size="md" variant="secondary">
          Show this to your conversation partner so they can scan and identify
          themselves. They need the L4RPCH3KR app installed.
        </ThemedText>
      </View>

      <View
        style={[
          styles.qrBox,
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

        {state === 'showing' && token && (
          <View style={{ alignItems: 'center', gap: spacing[3] }}>
            {/* QR placeholder — swap for react-native-qrcode-svg */}
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
                QR placeholder{'\n'}token:
              </ThemedText>
              <ThemedText
                size="sm"
                style={{ textAlign: 'center', fontFamily: 'Courier', marginTop: 4 }}
              >
                {token}
              </ThemedText>
            </View>
            <ThemedText size="xs" variant="muted">
              Auto-refreshes every 60s
            </ThemedText>
          </View>
        )}

        {state === 'consumed' && (
          <View style={{ alignItems: 'center', gap: spacing[3] }}>
            <ThemedText size="3xl">✓</ThemedText>
            <ThemedText size="lg" weight="semibold" style={{ color: colors.accent.default }}>
              Partner connected!
            </ThemedText>
            <ThemedText size="sm" variant="secondary" style={{ textAlign: 'center' }}>
              They've been identified. Switch to Live to monitor the session.
            </ThemedText>
          </View>
        )}

        {state === 'error' && (
          <ThemedText size="sm" variant="secondary" style={{ textAlign: 'center' }}>
            Couldn't generate QR. Tap Refresh to try again.
          </ThemedText>
        )}
      </View>

      {(state === 'showing' || state === 'error') && (
        <Button
          label="Refresh QR"
          variant="ghost"
          onPress={fetchToken}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  qrBox: {
    borderWidth: 1,
    alignItems: 'center',
    minHeight: 260,
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
