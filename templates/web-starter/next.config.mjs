/**
 * Next.js configuration.
 *
 * Sane defaults for a deploy-ready (Vercel) streaming-chat starter. There is no
 * business logic here — add only what your deployment actually needs.
 *
 * @type {import('next').NextConfig}
 */
const nextConfig = {
  reactStrictMode: true,
  // TODO: add your production tweaks here, e.g.
  //   - `images: { remotePatterns: [...] }` if you render remote images
  //   - `async headers()` / `async redirects()` for security headers or routing
  //   - `output: "standalone"` if you deploy as a container rather than to Vercel
};

export default nextConfig;
