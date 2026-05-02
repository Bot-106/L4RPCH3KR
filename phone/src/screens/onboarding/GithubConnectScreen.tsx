import React, { useState } from 'react';
import { View, Alert } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { Screen, Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { getGithubStartUrl, getMe } from '@/services/api';
import { useAuthStore } from '@/stores/auth';
import type { OnboardingStackParamList } from '@/navigation/RootNavigator';

type Props = NativeStackScreenProps<OnboardingStackParamList, 'GithubConnect'>;

export function GithubConnectScreen({ navigation }: Props) {
  const { spacing } = useTheme();
  const { updateUser } = useAuthStore();
  const [loading, setLoading] = useState(false);

  async function handleConnectGitHub() {
    setLoading(true);
    try {
      // The backend will redirect back to our deep link after the OAuth dance
      const redirectUri = 'larpchekr://auth/github/callback';
      const url = getGithubStartUrl(redirectUri);
      const result = await WebBrowser.openAuthSessionAsync(url, redirectUri);

      if (result.type === 'success') {
        // Backend has stored github_login; refresh user
        const { user } = await getMe();
        updateUser(user);
        if (user.github_login) {
          navigation.navigate('VoiceCalibration');
        } else {
          Alert.alert('GitHub connect failed', 'Please try again.');
        }
      }
    } catch (e: unknown) {
      Alert.alert('Error', e instanceof Error ? e.message : 'Could not connect GitHub.');
    } finally {
      setLoading(false);
    }
  }

  function handleSkip() {
    navigation.navigate('VoiceCalibration');
  }

  return (
    <Screen style={{ justifyContent: 'center', gap: spacing[6] }}>
      <View style={{ gap: spacing[2] }}>
        <ThemedText size="2xl" weight="bold">
          Connect GitHub
        </ThemedText>
        <ThemedText size="md" variant="secondary">
          We use your public GitHub profile to verify claims others make about
          their engineering experience. Nothing is posted on your behalf.
        </ThemedText>
      </View>

      <View style={{ gap: spacing[3] }}>
        <Button
          label="Connect GitHub"
          onPress={handleConnectGitHub}
          loading={loading}
        />
        <Button
          label="Skip for now"
          variant="ghost"
          onPress={handleSkip}
          disabled={loading}
        />
      </View>

      <ThemedText size="xs" variant="muted" style={{ textAlign: 'center' }}>
        Read-only access. We only read your public repos, languages, and employment
        history from your profile.
      </ThemedText>
    </Screen>
  );
}
