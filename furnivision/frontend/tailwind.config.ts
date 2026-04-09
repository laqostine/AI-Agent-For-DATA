import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        display: ['Playfair Display', 'Georgia', 'serif'],
      },
      colors: {
        surface: {
          50: '#FAFAF8',
          100: '#F5F0EB',
          200: '#E8E2DB',
          700: '#1C1C1F',
          800: '#141416',
          900: '#0C0C0E',
          950: '#080809',
        },
        accent: {
          DEFAULT: '#C4A265',
          light: '#D4B87A',
          dark: '#A88B52',
          muted: '#C4A26530',
        },
        success: '#4ADE80',
        warning: '#FBBF24',
        danger: '#F87171',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s ease-out',
        'slide-up': 'slideUp 0.4s ease-out',
        'pulse-glow': 'pulseGlow 3s ease-in-out infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 8px rgba(196, 162, 101, 0.15)' },
          '50%': { boxShadow: '0 0 24px rgba(196, 162, 101, 0.35)' },
        },
        shimmer: {
          '0%': { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
      },
      boxShadow: {
        'glow': '0 0 20px rgba(196, 162, 101, 0.15)',
        'glow-lg': '0 0 40px rgba(196, 162, 101, 0.2)',
        'inner-glow': 'inset 0 1px 0 rgba(255,255,255,0.04)',
        'card': '0 1px 3px rgba(0,0,0,0.3), 0 8px 24px rgba(0,0,0,0.15)',
        'card-hover': '0 2px 6px rgba(0,0,0,0.4), 0 12px 32px rgba(0,0,0,0.2)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'shimmer-gradient': 'linear-gradient(90deg, transparent 0%, rgba(196,162,101,0.06) 50%, transparent 100%)',
      },
    },
  },
  plugins: [],
};

export default config;
