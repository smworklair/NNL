import type { NextConfig } from "next";

/* Ядро NNL (Python) живёт отдельно: пока это функция на Vercel старого сайта. Адрес меняется переменной NNL_API. */
const API = process.env.NNL_API ?? "https://nnl-api.vercel.app";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
};

export default nextConfig;
