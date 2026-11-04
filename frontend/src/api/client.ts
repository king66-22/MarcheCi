import axios from 'axios'

export const api = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api' })

// Auth : ajoute le JWT si présent
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('marcheci_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 401 : purge de session (l'utilisateur est dirigé vers /connexion via le contexte)
api.interceptors.response.use(
  (resp) => resp,
  (err) => {
    if (err.response?.status === 401 && !String(err.config.url).includes('/auth/login')) {
      localStorage.removeItem('marcheci_token')
    }
    return Promise.reject(err)
  },
)
