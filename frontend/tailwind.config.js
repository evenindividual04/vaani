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
          base:      "#0A0A0A",
          primary:   "#111111",
          secondary: "#161616",
          elevated:  "#1C1C1C",
          hover:     "#262626",
          active:    "#333333",
        },
        border: {
          DEFAULT: "#2A2A2A",
          bright:  "#3E3E3E",
          focus:   "#52525B",
        },
        text: {
          primary:   "#FAFAFA",
          secondary: "#A1A1AA",
          muted:     "#71717A",
          dim:       "#52525B",
        },
        teal:  { DEFAULT: "#2DD4BF", dim: "rgba(45, 212, 191, 0.1)" },
        amber: { DEFAULT: "#FBBF24", dim: "rgba(251, 191, 36, 0.1)" },
        green: { DEFAULT: "#34D399", dim: "rgba(52, 211, 153, 0.1)" },
        danger:{ DEFAULT: "#F87171", dim: "rgba(248, 113, 113, 0.1)" },
        blue:  { DEFAULT: "#60A5FA", dim: "rgba(96, 165, 250, 0.1)" },
        indigo:{ DEFAULT: "#818CF8", dim: "rgba(129, 140, 248, 0.1)" },
        latency: {
          fast: "#00E676",
          ok:   "#F5A623",
          slow: "#FF4545",
        },
      },
      fontFamily: {
        sans:      ["Inter", "IBM Plex Sans", "sans-serif"],
        condensed: ["IBM Plex Sans Condensed", "sans-serif"],
        mono:      ["JetBrains Mono", "IBM Plex Mono", "monospace"],
      },
      borderRadius: {
        DEFAULT: "8px",
        lg: "12px",
        xl: "16px",
      },
      animation: {
        "pulse-glow":  "pulse-glow 2s ease-in-out infinite",
        "pulse-dot":   "pulse-dot 1.5s ease-in-out infinite",
        "ping-ring":   "ping-ring 1.5s cubic-bezier(0,0,0.2,1) infinite",
        "fade-in-up":  "fade-in-up 0.4s ease-out forwards",
        "fade-in":     "fade-in 0.3s ease-out forwards",
        "slide-left":  "slide-in-left 0.3s ease-out forwards",
        "shimmer":     "shimmer 1.6s ease-in-out infinite",
        "spin-slow":   "spin-slow 3s linear infinite",
        "breathe":     "breathe 2s ease-in-out infinite",
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
          to:   { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to:   { opacity: "1" },
        },
        "slide-in-left": {
          from: { opacity: "0", transform: "translateX(-12px)" },
          to:   { opacity: "1", transform: "translateX(0)" },
        },
        "shimmer": {
          from: { backgroundPosition: "200% 0" },
          to:   { backgroundPosition: "-200% 0" },
        },
        "spin-slow": {
          from: { transform: "rotate(0deg)" },
          to:   { transform: "rotate(360deg)" },
        },
        "breathe": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
      },
      boxShadow: {
        "panel": "0 1px 2px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.02)",
        "panel-hover": "0 4px 12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)",
      },
    },
  },
  plugins: [],
};


