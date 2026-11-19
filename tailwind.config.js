/** @type {import('tailwindcss').Config} */
const defaultTheme = require("tailwindcss/defaultTheme");

/*
  Electric Blue on a neutral shell: #F0F0F2 canvas, white cards and white sidebar,
  with the blues (#86FAF2 #30E7ED #00A6D7 #0058B3 #001B87) on everything you can
  act on. Only the bottom two blues clear 4.5:1 with white text, so those are the
  button and header fills; #00A6D7 is a non-text accent and the aqua pair are
  tints.

  The templates are full of `teal-*` and `slate-*` utilities written before any of
  these palettes existed. Rather than rewrite forty templates, the two ramps are
  redefined here: `teal` becomes the near-blacks used for buttons and active state,
  `slate` becomes the neutral greys. Every existing `bg-teal-700` and
  `text-slate-500` then follows the palette.

  The structural tokens live in :root at the top of templates/_components.css;
  these ramps and those tokens are kept in step by hand.

  Red, amber and green are left alone on purpose: an abnormal result, an overdue
  call and a destructive button have to keep their usual meaning.
*/
const electricBlue = {
  50: "#EAFDFC",
  100: "#D2F9F6",
  200: "#86FAF2",  // palette
  300: "#30E7ED",  // palette
  400: "#00C8E6",
  500: "#00A6D7",  // palette
  600: "#0077C4",
  700: "#0058B3",  // palette
  800: "#003E95",
  900: "#001B87",  // palette
  950: "#001160",
};

const neutral = {
  50: "#FAFAFA",
  100: "#F4F4F5",
  200: "#E7E7EA", // borders
  300: "#D4D4D8",
  400: "#A1A1AA",
  500: "#66666E", // muted text, 4.5:1 on the canvas
  600: "#52525B",
  700: "#3F3F46",
  800: "#27272A", // body text
  900: "#18181B",
  950: "#09090B",
};

module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py"],
  theme: {
    extend: {
      colors: {
        teal: electricBlue,
        slate: neutral,
        canvas: "#F0F0F2",
        accent: { DEFAULT: "#00A6D7", dark: "#0058B3", bg: "#EAFDFC", ink: "#001B87" },
      },
      fontFamily: {
        // Inter comes from Google Fonts (templates/_assets.html); the stack after it is
        // what the browser shows while the webfont loads, or if Google is unreachable.
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
        // Headings only - see the type scale in templates/_components.css.
        display: ["Space Grotesk", ...defaultTheme.fontFamily.sans],
        // Public site only, from 1mg: Poppins reads, Figtree acts. Loaded in
        // templates/public/base.html, not in the staff shell.
        poppins: ["Poppins", ...defaultTheme.fontFamily.sans],
        figtree: ["Figtree", ...defaultTheme.fontFamily.sans],
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
