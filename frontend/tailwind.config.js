/** @type {import('tailwindcss').Config} */
export default {
  // Tailwind v4 uses automatic content detection
  // Content paths are still useful for explicit scanning
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  // Theme customization moved to CSS with @theme directive in v4
  // Keep minimal config for backward compatibility
  theme: {
    extend: {},
  },
  plugins: [],
}
