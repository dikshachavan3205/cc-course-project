/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        base: "#00002A",
        surface: "#1A3F75",
        elevated: "#22497F",
        "border-mid": "#4D728F",
        muted: "#8FB0C9",
        primary: "#C9DAE8",
        "risk-low": "#5FBF8F",
        "risk-medium": "#E0A84D",
        "risk-high": "#E0654D",
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        lg: "var(--radius-lg)",
      },
      boxShadow: {
        hero: "var(--shadow-hero)",
      },
      fontFamily: {
        sans: ['"Space Grotesk"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: "12px",
        sm: "14px",
        base: "16px",
        lg: "20px",
        xl: "28px",
        "2xl": "44px",
      },
    },
  },
  plugins: [],
};