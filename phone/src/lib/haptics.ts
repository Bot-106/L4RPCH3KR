// Phone haptic is the secondary cue (Pi haptic is primary).
// Map severity to a light feedback type — don't over-engineer patterns.
import * as Haptics from 'expo-haptics';
import type { Severity } from '@/contracts';

export async function triggerFlagHaptic(severity: Severity): Promise<void> {
  switch (severity) {
    case 'low':
      // Quiet — selection only
      await Haptics.selectionAsync();
      break;
    case 'medium':
      // Single notification
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
      break;
    case 'high':
      // Strong notification
      await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      break;
  }
}

export async function triggerImpact(
  style: Haptics.ImpactFeedbackStyle = Haptics.ImpactFeedbackStyle.Medium,
): Promise<void> {
  await Haptics.impactAsync(style);
}
