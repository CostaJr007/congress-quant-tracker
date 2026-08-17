const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/politicians/:path*", destination: `${API}/politicians/:path*` },
    ];
  },
};

export default nextConfig;
