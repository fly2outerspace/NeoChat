import type { NextConfig } from "next";

const isProd = process.env.NODE_ENV === 'production';

const nextConfig: NextConfig = {
  // 静态导出配置（仅生产）
  ...(isProd ? {
    output: 'export',
    distDir: 'out',
    trailingSlash: true,
    // 关键：使用相对资源路径，确保 file:// 下可以正确加载
    assetPrefix: './',
    basePath: '',
  } : {}),
  
  // Disable image optimization (not supported in static export)
  images: {
    unoptimized: true,
  },
  
  // Note: headers() is not supported in static export mode
  // Cache control is handled via meta tags in layout.tsx and fetch headers in API calls
};

export default nextConfig;
