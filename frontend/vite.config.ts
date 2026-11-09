import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Proxy de dev : les chemins /api/* sont réécrits exactement comme le fera Nginx en prod.
// En production, Nginx sert le build et route /api/<svc>/ vers chaque microservice.
const servicePorts: Record<string, number> = {
  catalogue: 5211,
  utilisateurs: 5212,
  commandes: 5213,
  notifications: 5215,
}
const proxy: Record<string, object> = {}
for (const [svc, port] of Object.entries(servicePorts)) {
  proxy[`/api/${svc}`] = {
    target: `http://127.0.0.1:${port}`,
    changeOrigin: true,
    rewrite: (p: string) => p.replace(`/api/${svc}`, ''),
  }
}
// Photos produits en développement : le service catalogue expose /media/<fichier>.
proxy['/media'] = { target: 'http://127.0.0.1:5211', changeOrigin: true }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy },
})
