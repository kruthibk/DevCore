/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        space: {
          950: "#050811",
          900: "#0a101f",
          850: "#0f172a",
          800: "#131e36",
          700: "#1e2d4d",
        },
        telemetry: {
          cyan: "#22d3ee",
          emerald: "#10b981",
          amber: "#f59e0b",
          crimson: "#ef4444",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
