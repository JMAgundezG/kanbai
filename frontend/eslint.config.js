import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'
import tseslint from 'typescript-eslint'

export default tseslint.config(
  // Generated from the backend's OpenAPI: linting it makes no sense.
  { ignores: ['dist', 'src/api/schema.d.ts'] },
  js.configs.recommended,
  tseslint.configs.recommendedTypeChecked,
  // 7.x keeps the eslintrc-shaped config at the top level; the flat one lives here.
  reactHooks.configs.flat['recommended-latest'],
  reactRefresh.configs.vite,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
  {
    files: ['vite.config.ts'],
    languageOptions: { globals: globals.node },
  },
  {
    // This config file itself is plain JS and belongs to no tsconfig project, so
    // the type-aware rules cannot run on it.
    files: ['**/*.js'],
    extends: [tseslint.configs.disableTypeChecked],
  },
)
