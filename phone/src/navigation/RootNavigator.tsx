import React, { useEffect } from 'react';
import { ActivityIndicator, View } from 'react-native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';

import { useAuthStore } from '@/stores/auth';
import { getMe } from '@/services/api';
import { useTheme } from '@/theme/ThemeProvider';

// Onboarding
import { SignInScreen } from '@/screens/onboarding/SignInScreen';
import { GithubConnectScreen } from '@/screens/onboarding/GithubConnectScreen';
import { VoiceCalibrationScreen } from '@/screens/onboarding/VoiceCalibrationScreen';
import { PiPairScreen } from '@/screens/onboarding/PiPairScreen';

// Main tabs
import { LiveScreen } from '@/screens/live/LiveScreen';
import { ShowQrScreen } from '@/screens/pair/ShowQrScreen';
import { ScanQrScreen } from '@/screens/pair/ScanQrScreen';
import { RecapScreen } from '@/screens/recap/RecapScreen';

// Param lists

export type RootStackParamList = {
  MagicLinkCallback: { token: string };
  Onboarding: undefined;
  Main: undefined;
};

export type OnboardingStackParamList = {
  SignIn: undefined;
  GithubConnect: undefined;
  VoiceCalibration: undefined;
  PiPair: undefined;
};

export type MainTabParamList = {
  Live: undefined;
  ShowQr: undefined;
  ScanQr: undefined;
  Recap: { sessionId?: string };
};

const Root = createNativeStackNavigator<RootStackParamList>();
const Onboarding = createNativeStackNavigator<OnboardingStackParamList>();
const Tab = createBottomTabNavigator<MainTabParamList>();

function OnboardingNavigator() {
  const user = useAuthStore((s) => s.user);

  // Determine which onboarding step to start at
  let initialRoute: keyof OnboardingStackParamList = 'SignIn';
  if (user) {
    if (!user.github_login) initialRoute = 'GithubConnect';
    else if (!user.voice_calibration_id) initialRoute = 'VoiceCalibration';
    else initialRoute = 'PiPair';
  }

  return (
    <Onboarding.Navigator
      initialRouteName={initialRoute}
      screenOptions={{ headerShown: false }}
    >
      <Onboarding.Screen name="SignIn" component={SignInScreen} />
      <Onboarding.Screen name="GithubConnect" component={GithubConnectScreen} />
      <Onboarding.Screen name="VoiceCalibration" component={VoiceCalibrationScreen} />
      <Onboarding.Screen name="PiPair" component={PiPairScreen} />
    </Onboarding.Navigator>
  );
}

function MainTabs() {
  const { colors } = useTheme();
  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: colors.bg.surface,
          borderTopColor: colors.border.default,
        },
        tabBarActiveTintColor: colors.accent.default,
        tabBarInactiveTintColor: colors.text.muted,
      }}
    >
      <Tab.Screen name="Live" component={LiveScreen} options={{ title: 'Live' }} />
      <Tab.Screen name="ShowQr" component={ShowQrScreen} options={{ title: 'My QR' }} />
      <Tab.Screen name="ScanQr" component={ScanQrScreen} options={{ title: 'Scan' }} />
      <Tab.Screen
        name="Recap"
        component={RecapScreen}
        initialParams={{}}
        options={{ title: 'Recap' }}
      />
    </Tab.Navigator>
  );
}

function isOnboardingComplete(user: ReturnType<typeof useAuthStore>['user']): boolean {
  if (!user) return false;
  return !!(user.github_login && user.voice_calibration_id);
  // pi_token is set server-side after Pi scans the QR — we consider onboarding complete
  // once voice calibration is done, and let PiPair be accessible from Live mode.
}

export function RootNavigator() {
  const { jwt, user, isLoading, updateUser } = useAuthStore();
  const { colors } = useTheme();

  useEffect(() => {
    if (jwt && !user) {
      getMe().then(({ user: me }) => updateUser(me)).catch(() => {});
    }
  }, [jwt, user, updateUser]);

  if (isLoading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg.canvas, alignItems: 'center', justifyContent: 'center' }}>
        <ActivityIndicator color={colors.accent.default} />
      </View>
    );
  }

  const showMain = jwt && user && isOnboardingComplete(user);

  return (
    <Root.Navigator screenOptions={{ headerShown: false }}>
      {showMain ? (
        <Root.Screen name="Main" component={MainTabs} />
      ) : (
        <Root.Screen name="Onboarding" component={OnboardingNavigator} />
      )}
      {/* MagicLinkCallback is accessible regardless of auth state */}
      <Root.Screen name="MagicLinkCallback" component={SignInScreen} />
    </Root.Navigator>
  );
}
