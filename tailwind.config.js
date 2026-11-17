/** @type {import('tailwindcss').Config} */
const defaultTheme = require("tailwindcss/defaultTheme");

/*
  "Matcha Latte" palette:
    #F4F1E8 background  #C9D6A3 surface  #6B8F47 secondary
    #E8B87A accent      #2F3B24 primary / text

  The templates are full of `teal-*` and `slate-*` utilities written before this
  palette existed. Rather than rewrite forty templates, the two ramps are
  redefined here: `teal` becomes the matcha greens and `slate` becomes warm
  neutrals that sit with the cream instead of fighting it. Every existing
  `bg-teal-700`, `text-slate-500` and so on then follows the palette.

  The structural tokens live in :root at the top of templates/_components.css;
  these two ramps and those tokens are kept in step by hand.

  Red, amber and emerald are left alone on purpose: an abnormal result, an
  overdue call and a destructive button have to keep their usual meaning.
*/
const matcha = {
  50: "#F4F1E8",  // palette background
  100: "#EEF2E2",
  200: "#D3DFB6",
  300: "#C9D6A3", // palette surface
  400: "#A5BE7B",
  500: "#83A357",
  600: "#6B8F47", // palette secondary
  700: "#5A7A3C", // button fills: 4.9:1 with white text
  800: "#4E6B34",
  900: "#2F3B24", // palette primary / text
  950: "#1E2617",
};

const warmGrey = {
  50: "#F7F5EE",
  100: "#EFEDE2",
  200: "#E0DED0", // borders
  300: "#CBC9B8",
  400: "#A8A693",
  500: "#6E6D58", // muted text, 4.7:1 on the cream
  600: "#5C5B49",
  700: "#53533F",
  800: "#3C3D2C", // body text
  900: "#2F3B24",
  950: "#191A10",
};

module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py"],
  theme: {
    extend: {
      colors: {
        teal: matcha,
        slate: warmGrey,
        canvas: "#F4F1E8",
        accent: { DEFAULT: "#E8B87A", bg: "#FBF0DF", ink: "#8A5A1E" },
      },
      fontFamily: {
        // Inter comes from Google Fonts (templates/_assets.html); the stack after it is
        // what the browser shows while the webfont loads, or if Google is unreachable.
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
