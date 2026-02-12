/** @type {import('next').NextConfig} */
const nextConfig = {
  allowedDevOrigins: [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://192.168.110.1",
    "http://192.168.110.1:3000",
    "http://172.30.1.82",
    "http://172.30.1.82:3000",
  ],
};

export default nextConfig;
