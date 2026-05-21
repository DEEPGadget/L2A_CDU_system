/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{html,svelte,js}'],
  theme: {
    extend: {
      // Palette anchored to docs/UI_Design.md (Color palette).
      colors: {
        cdu: {
          normal:   '#27ae60',
          warning:  '#e67e22',
          critical: '#e74c3c',
          l1:       '#1f77b4',
          l2:       '#9467bd',
          total:    '#8c564b',
          ambientT: '#e377c2',
          ambientH: '#17becf'
        }
      }
    }
  },
  plugins: []
};
