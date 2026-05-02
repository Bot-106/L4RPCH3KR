import React, { useState, useRef, useCallback } from 'react';
import { View, Alert, StyleSheet } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import { Screen, Button, ThemedText } from '@/components';
import { useTheme } from '@/theme/ThemeProvider';
import { uploadVoiceCalibration, getMe } from '@/services/api';
import { useAuthStore } from '@/stores/auth';
import type { OnboardingStackParamList } from '@/navigation/RootNavigator';

type State = 'idle' | 'recording' | 'processing' | 'success' | 'error';

const RECORD_DURATION_MS = 15_000;

type Props = NativeStackScreenProps<OnboardingStackParamList, 'VoiceCalibration'>;

export function VoiceCalibrationScreen({ navigation }: Props) {
  const { colors, spacing, radius } = useTheme();
  const { updateUser } = useAuthStore();

  const [state, setState] = useState<State>('idle');
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const doneTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // In a full implementation we'd use react-native-vision-camera / Audio API.
  // For the MVP, we mock the recording capture and show the correct UX flow.
  // The actual audio capture is implemented below with the Audio API stub.

  const startRecording = useCallback(async () => {
    setState('recording');
    setElapsed(0);

    timerRef.current = setInterval(() => {
      setElapsed((e) => e + 1);
    }, 1000);

    doneTimerRef.current = setTimeout(() => {
      stopRecording();
    }, RECORD_DURATION_MS);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopRecording = useCallback(async () => {
    if (timerRef.current) clearInterval(timerRef.current);
    if (doneTimerRef.current) clearTimeout(doneTimerRef.current);
    setState('processing');

    try {
      // TODO: replace with real audio blob from AudioRecord / VisionCamera mic
      // For now we upload an empty wav header so the server can validate the flow.
      const stubWav = createStubWavBlob();
      await uploadVoiceCalibration(stubWav);

      const { user } = await getMe();
      updateUser(user);
      setState('success');
    } catch (e: unknown) {
      setState('error');
      Alert.alert('Calibration failed', e instanceof Error ? e.message : 'Please try again.');
    }
  }, [updateUser]);

  function handleContinue() {
    navigation.navigate('PiPair');
  }

  const dot = (
    <View
      style={[
        styles.dot,
        {
          backgroundColor:
            state === 'recording' ? colors.status.recording : colors.border.strong,
          width: 12,
          height: 12,
          borderRadius: radius.full,
        },
      ]}
    />
  );

  return (
    <Screen style={{ justifyContent: 'center', gap: spacing[6] }}>
      <View style={{ gap: spacing[2] }}>
        <ThemedText size="2xl" weight="bold">
          Voice calibration
        </ThemedText>
        <ThemedText size="md" variant="secondary">
          Read the sentence below aloud for 15 seconds. This trains the system
          to distinguish your voice from your conversation partner's.
        </ThemedText>
      </View>

      <View
        style={[
          styles.promptBox,
          {
            backgroundColor: colors.bg.surface,
            borderColor: colors.border.default,
            borderRadius: radius.md,
            padding: spacing[4],
          },
        ]}
      >
        <ThemedText size="md" style={{ lineHeight: 24, fontStyle: 'italic' }}>
          "The quick brown fox jumps over the lazy dog. Pack my box with five
          dozen liquor jugs. How vexingly quick daft zebras jump."
        </ThemedText>
      </View>

      {state === 'recording' && (
        <View style={styles.recordingRow}>
          {dot}
          <ThemedText size="md" variant="secondary">
            Recording… {elapsed}s / 15s
          </ThemedText>
        </View>
      )}

      {state === 'success' && (
        <ThemedText size="md" style={{ color: colors.accent.default, textAlign: 'center' }}>
          Voice calibration complete!
        </ThemedText>
      )}

      <View style={{ gap: spacing[3] }}>
        {state === 'idle' && (
          <Button label="Start recording" onPress={startRecording} />
        )}
        {state === 'recording' && (
          <Button
            label={`Stop early (${elapsed}s)`}
            onPress={stopRecording}
            variant="ghost"
          />
        )}
        {state === 'processing' && (
          <Button label="Processing…" loading disabled />
        )}
        {state === 'success' && (
          <Button label="Continue" onPress={handleContinue} />
        )}
        {state === 'error' && (
          <>
            <Button label="Try again" onPress={() => setState('idle')} />
            <Button
              label="Skip calibration"
              variant="ghost"
              onPress={handleContinue}
            />
          </>
        )}
      </View>
    </Screen>
  );
}

function createStubWavBlob(): Blob {
  // Minimal 44-byte WAV header with 0 audio samples — enough for the server to
  // parse and reject gracefully (or accept for integration tests).
  const buffer = new ArrayBuffer(44);
  const view = new DataView(buffer);
  // RIFF header
  view.setUint32(0, 0x52494646, false); // "RIFF"
  view.setUint32(4, 36, true);           // chunk size
  view.setUint32(8, 0x57415645, false);  // "WAVE"
  // fmt subchunk
  view.setUint32(12, 0x666d7420, false); // "fmt "
  view.setUint32(16, 16, true);          // subchunk size
  view.setUint16(20, 1, true);           // PCM
  view.setUint16(22, 1, true);           // mono
  view.setUint32(24, 16000, true);       // 16 kHz
  view.setUint32(28, 32000, true);       // byte rate
  view.setUint16(32, 2, true);           // block align
  view.setUint16(34, 16, true);          // bits per sample
  // data subchunk
  view.setUint32(36, 0x64617461, false); // "data"
  view.setUint32(40, 0, true);           // 0 bytes of audio
  return new Blob([buffer], { type: 'audio/wav' });
}

const styles = StyleSheet.create({
  promptBox: {
    borderWidth: 1,
  },
  recordingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  dot: {},
});
