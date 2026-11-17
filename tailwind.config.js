/** @type {import('tailwindcss').Config} */
const defaultTheme = require("tailwindcss/defaultTheme");

module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py"],
  theme: {
    extend: {
      fontFamily: {
        // Inter comes from Google Fonts (templates/_assets.html); the stack after it is
        // what the browser shows while the webfont loads, or if Google is unreachable.
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
