import type { Config } from 'tailwindcss';

export default {
  content: ['./app/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Rayara Authentic Backlit Bronze & Travertine Palette
        bronze: {
          DEFAULT: '#2a1810',
          dark: '#1c100a',
          light: '#3e2417',
          surface: '#4a2d1d',
        },
        // Backlight illuminated amber & golden glow
        amber: {
          glow: '#f5a623',
          warm: '#e59a38',
          deep: '#d97d26',
        },
        // Warm Travertine Limestone Sand
        sand: {
          50: '#faf6f0',
          100: '#f5efe6',
          200: '#ebe2d5',
          300: '#dfd2c0',
          400: '#cebeaa',
          500: '#a8957e',
        },
        // Mediterranean Olive Tree Accents
        olive: {
          light: '#6d7e5d',
          DEFAULT: '#4e5d42',
          dark: '#38432f',
          bg: '#eef3eb',
        },
        // Terracotta Earthenware
        terracotta: '#9e6b52',

        // Aliases for seamless component compatibility
        wine: '#2a1810',         // Updated from burgundy to signature Rayara Bronze
        cream: '#f5efe6',        // Warm limestone sand
        gold: '#d99b43',         // Illuminated amber gold
        ink: '#22140c',          // Deep espresso bronze ink
      },
      boxShadow: {
        glow: '0 12px 40px rgba(42, 24, 16, 0.12)',
        backlit: '0 0 25px rgba(229, 154, 56, 0.35), 0 8px 30px rgba(42, 24, 16, 0.12)',
        'backlit-lg': '0 0 45px rgba(229, 154, 56, 0.45), 0 15px 40px rgba(42, 24, 16, 0.18)',
      },
    },
  },
  plugins: [],
} satisfies Config;
