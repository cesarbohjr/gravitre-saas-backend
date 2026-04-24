/** @type {import('next').NextConfig} */
const nextConfig = {
  // FE-00: When BE is used, proxy /api/backend/* to FastAPI (see docs/phase-0/SA-00_EXECUTION_PLAN.md §11).
  // Uncomment and set destination for dev:
  // async rewrites() {
  //   return [{ source: '/api/backend/:path*', destination: 'http://localhost:8000/:path*' }];
  // },
};

module.exports = nextConfig;
