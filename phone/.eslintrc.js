module.exports = {
  root: true,
  extends: '@react-native',
  rules: {
    // Allow unused vars prefixed with _
    '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    // We don't use React.FC — prefer explicit return type or inference
    'react/react-in-jsx-scope': 'off',
  },
};
