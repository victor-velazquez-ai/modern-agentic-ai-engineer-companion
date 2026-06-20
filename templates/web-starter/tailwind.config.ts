import type { Config } from "tailwindcss";

/**
 * Tailwind configuration — minimal, clean chat styling out of the box.
 *
 * `content` lists the files Tailwind scans for class names. Add any new
 * directories you create that use Tailwind classes, or their styles won't ship.
 */
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    // TODO: add other directories here if you put Tailwind classes outside app/
  ],
  theme: {
    extend: {
      // TODO: your brand colors, fonts, and spacing go here.
      // e.g. colors: { brand: "#2563eb" }
    },
  },
  plugins: [],
};

export default config;
