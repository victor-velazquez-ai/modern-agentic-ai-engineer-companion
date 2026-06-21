import type { Config } from "tailwindcss";

/**
 * Tailwind configuration. `content` lists the files Tailwind scans for class
 * names — add new directories under app/ here or their styles won't ship.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
