/** @type {import('tailwindcss').Config} */
export default {
  // Tailwind v4 uses automatic content detection
  // Content paths are still useful for explicit scanning
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  // Theme customization moved to CSS with @theme directive in v4
  // Keep minimal config for backward compatibility
  theme: {
    extend: {
      // Custom animations for drag-and-drop
      animation: {
        'drop-success': 'drop-success 0.3s ease-out',
        'snap-back': 'snap-back 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'pulse-border': 'pulse-border 1.5s ease-in-out infinite',
        'ghost-float': 'ghost-float 0.2s ease-out',
      },
      keyframes: {
        'drop-success': {
          '0%': { transform: 'scale(1)', opacity: '1' },
          '50%': { transform: 'scale(1.05)', opacity: '0.8' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        'snap-back': {
          '0%': { transform: 'scale(1) rotate(0deg)', opacity: '1' },
          '50%': { transform: 'scale(0.95) rotate(-2deg)', opacity: '0.5' },
          '100%': { transform: 'scale(1) rotate(0deg)', opacity: '1' },
        },
        'pulse-border': {
          '0%, 100%': {
            borderColor: 'rgb(59 130 246 / 0.5)',
            boxShadow: '0 0 0 0 rgb(59 130 246 / 0.4)',
          },
          '50%': {
            borderColor: 'rgb(59 130 246 / 1)',
            boxShadow: '0 0 0 4px rgb(59 130 246 / 0.1)',
          },
        },
        'ghost-float': {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '0.95' },
        },
      },
    },
  },
  plugins: [],
}
