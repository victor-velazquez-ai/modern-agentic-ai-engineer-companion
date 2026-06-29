/**
 * Next.js configuration for the agentic-platform frontend.
 *
 * `output: "standalone"` so the app ships as a self-contained server bundle in a
 * container (it is deployed alongside the API, not to Vercel). Add production
 * tweaks (security headers, image domains) here as the platform needs them.
 *
 * @type {import('next').NextConfig}
 */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
};

export default nextConfig;
