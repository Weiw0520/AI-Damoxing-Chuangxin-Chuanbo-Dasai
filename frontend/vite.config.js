import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 开发时把 /api 代理到 Python 后端，前端代码里永远只写 /api/xxx，
// 不出现 127.0.0.1:8000 这种硬编码 —— 部署时也就不需要改代码。
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
    chunkSizeWarningLimit: 900,
    // 不清空 dist：这台机器的 F 盘没有可用的回收站，vite 清目录时会调 fs.rmSync，
    // 被安全删除垫片拦下后整次构建失败（"Some operations were aborted"）。
    // 代价是旧哈希文件会留在 dist/assets 里，不影响运行；要清理见 README。
    emptyOutDir: false,
  },
})
