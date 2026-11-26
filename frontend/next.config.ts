import type { NextConfig } from "next";

// Where the Django backend lives. Server-side only: the browser never talks to
// it directly, it talks to this Next.js app, which proxies (rewrites) to Django.
const BACKEND_URL = (process.env.BACKEND_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // Django URLs end in "/" (e.g. /products/list/). Matching that convention means
  // links between the Django pages and the Next.js pages keep working unchanged.
  trailingSlash: true,
  async rewrites() {
    return {
      // REST API → Django. Runs before Next.js routes are checked.
      beforeFiles: [{ source: "/api/:path*/", destination: `${BACKEND_URL}/api/:path*/` }],
      afterFiles: [],
      // Strangler migration: any URL Next.js doesn't serve (modules not rebuilt
      // yet, /static/, /media/, /admin/, …) is served by Django on the same domain,
      // so one session cookie works across both apps.
      // `:path*` drops a trailing slash, so match it explicitly (Django would
      // otherwise redirect /x → /x/ and loop). The second rule covers files
      // such as /static/css/app.css, which have no trailing slash.
      fallback: [
        { source: "/:path*/", destination: `${BACKEND_URL}/:path*/` },
        { source: "/:path*", destination: `${BACKEND_URL}/:path*` },
      ],
    };
  },
  async redirects() {
    return [
      { source: "/", destination: "/dashboard/", permanent: false },
      // Django's auth pages → the Next.js ones (query string, e.g. ?next=, is kept).
      { source: "/accounts/login/", destination: "/login/", permanent: false },
      { source: "/accounts/signup/", destination: "/signup/", permanent: false },
    ];
  },
};

export default nextConfig;
