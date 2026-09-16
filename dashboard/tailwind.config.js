/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        base:      'var(--bg-base)',
        surface:   'var(--bg-surface)',
        'border-mid': {
          DEFAULT: 'var(--border-hairline)',
          full:    'var(--border-mid)',
          strong:  'var(--border-strong)',
        },
        muted:     'var(--text-muted)',
        primary:   'var(--text-primary)',
        'risk-low':    'var(--risk-low)',
        'risk-medium': 'var(--risk-medium)',
        'risk-high':   'var(--risk-high)',
        'conn-on':     'var(--conn-on)',
        'conn-off':    'var(--conn-off)',
      },
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      fontSize: {
        xs:   ['var(--text-xs)',  { lineHeight: 'var(--leading-relaxed)' }],
        sm:   ['var(--text-sm)',  { lineHeight: 'var(--leading-relaxed)' }],
        base: ['var(--text-base)',{ lineHeight: 'var(--leading-normal)' }],
        lg:   ['var(--text-lg)',  { lineHeight: 'var(--leading-normal)' }],
        xl:   ['var(--text-xl)',  { lineHeight: 'var(--leading-snug)' }],
        '2xl': ['var(--text-2xl)',{ lineHeight: 'var(--leading-tight)' }],
      },
      borderRadius: {
        data:      'var(--radius-data)',
        prominent: 'var(--radius-prominent)',
      },
      keyframes: {
        'arc-fill': {
          '0%':   { strokeDashoffset: '251.2' },
          '100%': { strokeDashoffset: 'var(--arc-offset, 0)' },
        },
        'value-in': {
          '0%':   { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'arc-fill': 'arc-fill var(--duration-arc) var(--ease-arc) forwards',
        'value-in': 'value-in 0.6s var(--ease-value) forwards',
      },
    },
  },
  plugins: [],
};
