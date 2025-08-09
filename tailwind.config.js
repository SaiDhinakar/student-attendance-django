/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './Frontend/templates/**/*.html',
    './Authentication/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        'accent': 'var(--accent)',
        'primary': 'var(--primary)',
        'secondary': 'var(--secondary)',
        'background': 'var(--background)',
        'section-bg': 'var(--section-bg)',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'button-primary': 'var(--button-primary)',
        'button-secondary': 'var(--button-secondary)',
      }
    },
  },
  plugins: [],
}
