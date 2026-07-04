/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#17202a",
        muted: "#5b6776",
        line: "#d7dde5",
        panel: "#f7f9fb",
        brand: "#2563eb",
        success: "#16803c",
        danger: "#b42318",
        warning: "#a15c07"
      }
    }
  },
  plugins: [],
};
