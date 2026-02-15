import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    env: {
      VS_DATA_DIR: "./data",
      VS_LOGS_DIR: "./logs",
    },
  },
});
