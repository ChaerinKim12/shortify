import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 개발 서버에서 /api 요청을 백엔드(localhost:8000)로 전달한다.
// 이렇게 하면 프론트(5173)와 백엔드(8000) 주소가 달라도 CORS 문제가 생기지 않는다.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})