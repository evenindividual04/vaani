const path = require('path');

/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    path.join(__dirname, "./src/**/*.{js,ts,jsx,tsx,mdx}"),
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          base: "#080B0F",
          primary: "#0C1017",
          secondary: "#111820",
          elevated: "#171F2A",
          hover: "#1C2535",
          active: "#1E2D3D",
        },
        border: {
          DEFAULT: "rgba(255,255,255,0.07)",
          bright: "rgba(255,255,255,0.14)",
          glow: "rgba(0, 212, 200, 0.35)",
        },
        text: {
          primary: "#F0F4F8",
          secondary: "#8B9BB4",
          muted: "#4A5568",
          dim: "#2D3748",
        },
        teal: { DEFAULT: "#00D4C8", dim: "rgba(0,212,200,0.12)", glow: "rgba(0,212,200,0.25)" },
        amber: { DEFAULT: "#F5A623", dim: "rgba(245,166,35,0.12)" },
        green: { DEFAULT: "#00E676", dim: "rgba(0,230,118,0.12)" },
        danger: { DEFAULT: "#FF4545", dim: "rgba(255,69,69,0.12)" },
        blue: { DEFAULT: "#4C9EFF", dim: "rgba(76,158,255,0.12)" },
        latency: {
          fast: "#00E676",
          ok: "#F5A623",
          slow: "#FF4545",
        },
      },
      fontFamily: {
        sans: ["Inter", "IBM Plex Sans", "sans-serif"],
        condensed: ["IBM Plex Sans Condensed", "sans-serif"],
        mono: ["JetBrains Mono", "IBM Plex Mono", "monospace"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
        xl: "16px",
      },
      animation: {
        "pulse-glow": "pulse-glow 2s ease-in-out infinite",
        "pulse-dot": "pulse-dot 1.5s ease-in-out infinite",
        "ping-ring": "ping-ring 1.5s cubic-bezier(0,0,0.2,1) infinite",
        "fade-in-up": "fade-in-up 0.4s ease-out forwards",
        "fade-in": "fade-in 0.3s ease-out forwards",
        "slide-left": "slide-in-left 0.3s ease-out forwards",
        "shimmer": "shimmer 1.6s ease-in-out infinite",
        "spin-slow": "spin-slow 3s linear infinite",
        "breathe": "breathe 2s ease-in-out infinite",
      },
      keyframes: {
        "pulse-glow": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "pulse-dot": {
          "0%, 100%": { transform: "scale(1)", opacity: "1" },
          "50%": { transform: "scale(1.4)", opacity: "0.7" },
        },
        "ping-ring": {
          "0%": { transform: "scale(1)", opacity: "0.6" },
          "100%": { transform: "scale(2.5)", opacity: "0" },
        },
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-in-left": {
          from: { opacity: "0", transform: "translateX(-12px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
        "shimmer": {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        "spin-slow": {
          from: { transform: "rotate(0deg)" },
          to: { transform: "rotate(360deg)" },
        },
        "breathe": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      boxShadow: {
        "glow-teal": "0 0 12px rgba(0,212,200,0.25), 0 0 4px rgba(0,212,200,0.25)",
        "glow-amber": "0 0 12px rgba(245,166,35,0.3), 0 0 4px rgba(245,166,35,0.3)",
        "glow-green": "0 0 12px rgba(0,230,118,0.3), 0 0 4px rgba(0,230,118,0.3)",
        "glow-red": "0 0 12px rgba(255,69,69,0.3), 0 0 4px rgba(255,69,69,0.3)",
      },
    },
  },
  plugins: [],
};


