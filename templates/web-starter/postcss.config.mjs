/**
 * PostCSS configuration — wires Tailwind and autoprefixer into the build.
 * You normally never need to touch this.
 *
 * @type {import('postcss-load-config').Config}
 */
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};

export default config;
