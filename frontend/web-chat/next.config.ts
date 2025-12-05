import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Only enable static export in production build, not in dev mode
  ...(process.env.NODE_ENV === 'production' ? {
    output: 'export',
    distDir: 'out',
    trailingSlash: true,
  } : {}),
  
  // Disable image optimization (not supported in static export)
  images: {
    unoptimized: true,
  },
  
  // Note: headers() is not supported in static export mode
  // Cache control is handled via meta tags in layout.tsx and fetch headers in API calls
};

export default nextConfig;
