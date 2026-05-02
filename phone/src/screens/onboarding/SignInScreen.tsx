import React, { useState, useEffect } from 'react';
import { View, TextInput, StyleSheet, Alert } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { Screen, Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { requestMagicLink, exchangeMagicLinkToken } from '@/services/api';
import { useAuthStore } from '@/stores/auth';
import type { RootStackParamList, OnboardingStackParamList } from '@/navigation/RootNavigator';

// SignInScreen handles two cases:
// 1. Normal sign-in (initial email entry)
// 2. MagicLinkCallback deep link (when `token` is in route params)

type SignInProps =
  | NativeStackScreenProps<OnboardingStackParamList, 'SignIn'>
  | NativeStackScreenProps<RootStackParamList, 'MagicLinkCallback'>;

export function SignInScreen({ route, navigation }: SignInProps) {
  const { colors, spacing, radius, fontSize } = useTheme();
  const { signIn } = useAuthStore();

  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);
  const [manualToken, setManualToken] = useState('');
  const [loading, setLoading] = useState(false);

  // Handle deep link callback
  const deepLinkToken =
    'token' in (route.params ?? {}) ? (route.params as { token: string }).token : null;

  useEffect(() => {
    if (deepLinkToken) {
      handleTokenExchange(deepLinkToken);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkToken]);

  async function handleSendLink() {
    if (!email.trim()) return;
    setLoading(true);
    try {
      await requestMagicLink(email.trim().toLowerCase());
      setSent(true);
    } catch (e: unknown) {
      Alert.alert('Error', e instanceof Error ? e.message : 'Could not send magic link.');
    } finally {
      setLoading(false);
    }
  }

  async function handleTokenExchange(token: string) {
    setLoading(true);
    try {
      const { user, jwt } = await exchangeMagicLinkToken(token);
      await signIn(jwt, user);
      // Navigation driven by auth state in RootNavigator — no explicit push needed
    } catch (e: unknown) {
      Alert.alert('Sign-in failed', e instanceof Error ? e.message : 'Invalid or expired link.');
    } finally {
      setLoading(false);
    }
  }

  if (loading && deepLinkToken) {
    return (
      <Screen style={styles.center}>
        <ThemedText size="md" variant="secondary">Signing you in…</ThemedText>
      </Screen>
    );
  }

  return (
    <Screen style={styles.container}>
      <View style={styles.hero}>
        <ThemedText size="3xl" weight="bold" style={{ marginBottom: spacing[2] }}>
          L4RPCH3KR
        </ThemedText>
        <ThemedText size="md" variant="secondary" style={{ textAlign: 'center' }}>
          Real-time claim verification for hackathon conversations.
        </ThemedText>
      </View>

      {!sent ? (
        <View style={{ gap: spacing[3] }}>
          <ThemedText size="sm" variant="secondary">
            Enter your email to receive a magic link.
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
            placeholder="you@example.com"
            placeholderTextColor={colors.text.muted}
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            value={email}
            onChangeText={setEmail}
            onSubmitEditing={handleSendLink}
            returnKeyType="send"
          />
          <Button
            label="Send magic link"
            onPress={handleSendLink}
            loading={loading}
            disabled={!email.trim()}
          />
        </View>
      ) : (
        <View style={{ gap: spacing[4] }}>
          <ThemedText size="md" style={{ textAlign: 'center' }}>
            Check your email for a magic link. Tap it to continue.
          </ThemedText>
          <ThemedText size="sm" variant="secondary" style={{ textAlign: 'center' }}>
            Didn't get it? Paste the code below.
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
                fontFamily: 'Courier',
              },
            ]}
            placeholder="Paste token here"
            placeholderTextColor={colors.text.muted}
            autoCapitalize="none"
            autoCorrect={false}
            value={manualToken}
            onChangeText={setManualToken}
          />
          <Button
            label="Confirm"
            onPress={() => handleTokenExchange(manualToken.trim())}
            loading={loading}
            disabled={!manualToken.trim()}
          />
          <Button
            label="Use a different email"
            variant="ghost"
            onPress={() => { setSent(false); setManualToken(''); }}
          />
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  container: {
    justifyContent: 'center',
    gap: 32,
  },
  hero: {
    alignItems: 'center',
    gap: 8,
  },
  input: {
    borderWidth: 1,
  },
  center: {
    justifyContent: 'center',
    alignItems: 'center',
  },
});
