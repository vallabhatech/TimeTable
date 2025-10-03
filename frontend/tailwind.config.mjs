/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        'muli-bold': ['Muli-Bold', 'sans-serif'],
        'muli-semibold': ['Muli-SemiBold', 'sans-serif'],
        'muli-regular': ['Muli-Regular', 'sans-serif'],
      },
      colors: {
        // Base colors
        background: "#09090B",
        surface: "#18181B",
        border: "#27272A",
        
        // Text colors
        primary: "#F8FAFC",
        secondary: "#A1A1AA",
        
        // Accent colors
        accent: {
          cyan: "#22D3EE",
          pink: "#F471B5",
          green: "#4ADE80",
        },
        
        // Gradient pairs
        gradient: {
          'cyan-start': '#22D3EE',
          'cyan-end': '#0EA5E9',
          'pink-start': '#F471B5',
          'pink-end': '#E879F9',
          'purple-start': '#A78BFA',
          'purple-end': '#8B5CF6',
        }
      },
      spacing: {
        '128': '32rem',
        '144': '36rem',
      },
      borderRadius: {
        'xl': '1rem',
      },
      boxShadow: {
        'soft': '0 2px 15px -3px rgba(0, 0, 0, 0.07), 0 10px 20px -2px rgba(0, 0, 0, 0.04)',
      },
      animation: {
        'gradient-x': 'gradient-x 15s ease infinite',
        'gradient-y': 'gradient-y 15s ease infinite',
        'gradient-xy': 'gradient-xy 15s ease infinite',
        'pulse-slow': 'pulse 8s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        'gradient-y': {
          '0%, 100%': {
            'background-size': '400% 400%',
            'background-position': 'center top'
          },
          '50%': {
            'background-size': '200% 200%',
            'background-position': 'center center'
          }
        },
        'gradient-x': {
          '0%, 100%': {
            'background-size': '200% 200%',
            'background-position': 'left center'
          },
          '50%': {
            'background-size': '200% 200%',
            'background-position': 'right center'
          }
        },
        'gradient-xy': {
          '0%, 100%': {
            'background-size': '400% 400%',
            'background-position': 'left center'
          },
          '50%': {
            'background-size': '200% 200%',
            'background-position': 'right center'
          }
        }
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
};
