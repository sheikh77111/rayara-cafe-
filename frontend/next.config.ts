import type { NextConfig } from 'next';

const backendTarget = process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000/api';
const cleanBackend = backendTarget.replace(/\/+$/, '');

const nextConfig: NextConfig = {
  skipTrailingSlashRedirect: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${cleanBackend}/:path*`,
      },
    ];
  },
};

export default nextConfig;
