import type { LinkingOptions } from '@react-navigation/native';
import { DEEP_LINK_SCHEME } from '@env';
import type { RootStackParamList } from './RootNavigator';

export const linking: LinkingOptions<RootStackParamList> = {
  prefixes: [`${DEEP_LINK_SCHEME}://`],
  config: {
    screens: {
      // Magic-link deep link: larpchekr://auth?token=...
      MagicLinkCallback: {
        path: 'auth',
        parse: {
          token: (token: string) => token,
        },
      },
    },
  },
};
