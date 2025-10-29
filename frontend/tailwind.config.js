/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Quipflip Brand Colors
        'quip-turquoise': '#10B4A4',
        'quip-teal': '#0A5852', // Darkened from #0E6F6A for better contrast
        'quip-teal-light': '#E8F5F4', // Very light teal for tile backgrounds
        'quip-orange': '#FF9A3D',
        'quip-orange-deep': '#E26A00',
        'quip-cream': '#FFF6EE',
        'quip-navy': '#0B2137',
        // Quest category palette
        'quest-streak': '#FF9A3D',
        'quest-quality': '#FF6B6B',
        'quest-quality-dark': '#D64545',
        'quest-quality-light': '#FF8A8A',
        'quest-milestone': '#FFC857',
        'quest-milestone-dark': '#C88200',
        'quest-milestone-light': '#FFB347',
      },
      fontFamily: {
        'display': ['Poppins', 'Inter', 'system-ui', 'sans-serif'],
        'sans': ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        'tile': '20px',
      },
      boxShadow: {
        'tile': '0 12px 24px rgba(11, 33, 55, 0.18)',
        'tile-sm': '0 4px 12px rgba(11, 33, 55, 0.12)',
      },
      animation: {
        'flip': 'flip 0.6s ease-in-out',
        'shuffle': 'shuffle 0.4s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        flip: {
          '0%': { transform: 'rotateY(0deg) scale(1)' },
          '50%': { transform: 'rotateY(90deg) scale(0.95)' },
          '100%': { transform: 'rotateY(0deg) scale(1)' },
        },
        shuffle: {
          '0%, 100%': { transform: 'translateX(0) rotate(0deg)' },
          '25%': { transform: 'translateX(-4px) rotate(-2deg)' },
          '75%': { transform: 'translateX(4px) rotate(2deg)' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
