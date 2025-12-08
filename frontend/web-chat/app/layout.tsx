'use client';

import { useEffect } from "react";
import { App, ConfigProvider } from "antd";
import { antdThemeConfig } from "@/lib/antdTheme";
import "antd/dist/reset.css";
import "./globals.css";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Set document title and meta on client side (compatible with static export)
  useEffect(() => {
    document.title = "NeoChat - AI Agent Frontend";
    
    // Set meta description
    let metaDescription = document.querySelector('meta[name="description"]');
    if (!metaDescription) {
      metaDescription = document.createElement('meta');
      metaDescription.setAttribute('name', 'description');
      document.head.appendChild(metaDescription);
    }
    metaDescription.setAttribute('content', 'NeoChat frontend interface for AI agent conversations');
  }, []);

  return (
    <html lang="en">
      <head>
        <title>NeoChat - AI Agent Frontend</title>
        <meta name="description" content="NeoChat frontend interface for AI agent conversations" />
      </head>
      <body className="antialiased">
        <ConfigProvider theme={antdThemeConfig}>
          <App>
        {children}
          </App>
        </ConfigProvider>
      </body>
    </html>
  );
}
