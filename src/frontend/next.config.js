
// telling vscode to treat this file as a NextConfig file
/** @type {import('next').NextConfig} */
// import Node.js built-in 'path' module. Create absolute paths in a platform-safe way
const path = require('path');

// Disable ESLint during build time (next build). Need to come back to fix this. 
const nextConfig = {
  eslint: {
    ignoreDuringBuilds: true,
  },
  // To resolve the @lib alias to the src/lib directory
  webpack: (config) => {
    config.resolve.alias['@'] = path.resolve(__dirname, 'src');
    return config;
  },
};
// Exports the configuration object so Next.js can use it.
module.exports = nextConfig;
