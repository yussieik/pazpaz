/** @type {import('tailwindcss').Config} */
export default {
  // Tailwind v4 uses automatic content detection
  // Content paths are still useful for explicit scanning
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  // Theme customization moved to CSS with @theme directive in v4
  // Keep minimal config for backward compatibility
  theme: {
    extend: {
      // Custom typography for clinical documentation
      typography: ({ theme }) => ({
        clinical: {
          css: {
            '--tw-prose-body': theme('colors.slate[700]'),
            '--tw-prose-headings': theme('colors.slate[900]'),
            '--tw-prose-bold': theme('colors.slate[900]'),
            '--tw-prose-bullets': theme('colors.emerald[500]'),
            '--tw-prose-quotes': theme('colors.slate[500]'),
            '--tw-prose-links': theme('colors.emerald[600]'),
            '--tw-prose-code': theme('colors.slate[900]'),
            '--tw-prose-code-bg': theme('colors.slate[100]'),

            // Tighter spacing for clinical context
            maxWidth: 'none',
            fontSize: '0.875rem',
            lineHeight: '1.6',

            h1: {
              fontSize: '1.125rem',
              fontWeight: '700',
              marginTop: '1em',
              marginBottom: '0.5em',
            },
            h2: {
              fontSize: '1rem',
              fontWeight: '600',
              marginTop: '0.75em',
              marginBottom: '0.375em',
            },
            h3: {
              fontSize: '0.925rem',
              fontWeight: '600',
              marginTop: '0.5em',
              marginBottom: '0.25em',
            },
            p: {
              marginTop: '0.5em',
              marginBottom: '0.5em',
            },
            'ul, ol': {
              marginTop: '0.5em',
              marginBottom: '0.5em',
              paddingLeft: '1.25rem',
            },
            li: {
              marginTop: '0.25em',
              marginBottom: '0.25em',
            },
            strong: {
              color: theme('colors.slate[900]'),
              fontWeight: '600',
            },
            code: {
              color: theme('colors.slate[900]'),
              backgroundColor: theme('colors.slate[100]'),
              padding: '0.125rem 0.25rem',
              borderRadius: '0.25rem',
              fontSize: '0.875em',
              fontWeight: '500',
            },
            'code::before': {
              content: '""',
            },
            'code::after': {
              content: '""',
            },
          },
        },
      }),
      // Custom scales for micro-interactions
      scale: {
        98: '0.98',
        102: '1.02',
      },
      // Custom animations for drag-and-drop and micro-interactions
      animation: {
        'drop-success': 'drop-success 0.3s ease-out',
        'snap-back': 'snap-back 0.4s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'pulse-border': 'pulse-border 1.5s ease-in-out infinite',
        'ghost-float': 'ghost-float 0.2s ease-out',
        'bounce-in': 'bounce-in 0.5s cubic-bezier(0.68, -0.55, 0.265, 1.55)',
        'slide-in-right': 'slide-in-right 0.3s ease-out',
        'slide-down': 'slide-down 0.3s ease-out',
        shake: 'shake 0.4s ease-in-out',
        shimmer: 'shimmer 2s infinite linear',
        'modal-backdrop': 'modal-backdrop 0.2s ease-out',
        'modal-content': 'modal-content 0.3s ease-out',
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
        'bounce-in': {
          '0%': { transform: 'scale(0)', opacity: '0' },
          '50%': { transform: 'scale(1.1)', opacity: '1' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        'slide-in-right': {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-down': {
          '0%': { transform: 'translateY(-10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        shake: {
          '0%, 100%': { transform: 'translateX(0)' },
          '10%, 30%, 50%, 70%, 90%': { transform: 'translateX(-4px)' },
          '20%, 40%, 60%, 80%': { transform: 'translateX(4px)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-1000px 0' },
          '100%': { backgroundPosition: '1000px 0' },
        },
        'modal-backdrop': {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        'modal-content': {
          '0%': { transform: 'scale(0.95)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
}
