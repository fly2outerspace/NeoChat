import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable static export for packaging
  output: 'export',
  
  // Output directory for static files
  distDir: 'out',
  
  // Disable image optimization (not supported in static export)
  images: {
    unoptimized: true,
  },
  
  // Ensure trailing slashes for proper static file serving
  trailingSlash: true,
};

export default nextConfig;
