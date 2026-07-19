import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle (.next/standalone) so the Docker
  // image ships only the files it needs. Ignored by Vercel, which handles
  // the build natively.
  output: "standalone",
};

export default nextConfig;
