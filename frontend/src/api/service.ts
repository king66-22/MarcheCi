import { api } from './client'
import type {
  Product, ProductImage, ProductPage, Category, Order, OrderPage, OrderStatus, User, TokenResponse,
  NotificationRow, Role,
} from './types'

export const catalogueApi = {
  listProducts(params: { q?: string; category?: string; in_stock?: boolean; page?: number; page_size?: number }) {
    return api.get<ProductPage>('/catalogue/products', { params })
  },
  getProduct(id: number | string) {
    return api.get<Product>(`/catalogue/products/${id}`)
  },
  listCategories() {
    return api.get<Category[]>('/catalogue/categories')
  },
  // Espace commerçant : produits possédés (actifs et désactivés)
  mine() {
    return api.get<ProductPage>('/catalogue/products/mine', { params: { page_size: 100 } })
  },
  // Gestion (ADMIN ou COMMERCANT propriétaire)
  createProduct(data: Record<string, unknown>) {
    return api.post<Product>('/catalogue/products', data)
  },
  updateProduct(id: number, data: Record<string, unknown>) {
    return api.put<Product>(`/catalogue/products/${id}`, data)
  },
  deleteProduct(id: number) {
    return api.delete<Product>(`/catalogue/products/${id}`)
  },
  // Photos produits
  uploadProductImage(productId: number, file: File, onProgress?: (percent: number) => void) {
    const form = new FormData()
    form.append('file', file)
    return api.post<ProductImage>(`/catalogue/products/${productId}/images`, form, {
      onUploadProgress: (event) => {
        if (!onProgress || !event.total) return
        onProgress(Math.round((event.loaded / event.total) * 100))
      },
    })
  },
  deleteProductImage(productId: number, imageId: number) {
    return api.delete<ProductImage>(`/catalogue/products/${productId}/images/${imageId}`)
  },
  setProductCover(productId: number, imageId: number) {
    return api.post<ProductImage>(`/catalogue/products/${productId}/images/${imageId}/cover`)
  },
  adjustStock(id: number, delta: number) {
    return api.post<{ product_id: number; stock_after: number }>(
      `/catalogue/products/${id}/adjust-stock`,
      { delta },
    )
  },
  createCategory(data: { slug: string; name: string }) {
    return api.post<Category>('/catalogue/categories', data)
  },
  deleteCategory(id: number) {
    return api.delete<Category>(`/catalogue/categories/${id}`)
  },
}

export const usersApi = {
  register(data: {
    email: string
    password: string
    full_name: string
    phone?: string
    role?: 'CLIENT' | 'COMMERCANT'
  }) {
    return api.post<User>('/utilisateurs/auth/register', data)
  },
  login(email: string, password: string) {
    return api.post<TokenResponse>('/utilisateurs/auth/login', { email, password })
  },
  me() {
    return api.get<User>('/utilisateurs/users/me')
  },
  updateMe(data: { full_name?: string; phone?: string; current_password?: string; new_password?: string }) {
    return api.put<User>('/utilisateurs/users/me', data)
  },
  listAll(page = 1) {
    return api.get<User[]>('/utilisateurs/users', { params: { page } })
  },
  updateRole(id: number, role: Exclude<Role, 'ADMIN'>) {
    return api.patch<User>(`/utilisateurs/users/${id}/role`, { role })
  },
}

export const ordersApi = {
  create(data: {
    items: { product_id: number; quantity: number }[]
    delivery_address: string
    delivery_phone: string
  }) {
    return api.post<Order>('/commandes/orders', data)
  },
  mine(page = 1, statusFilter?: string) {
    return api.get<OrderPage>('/commandes/orders', {
      params: { page, page_size: 20, status: statusFilter || undefined },
    })
  },
  all(page = 1) {
    return api.get<OrderPage>('/commandes/orders', { params: { page, page_size: 50 } })
  },
  get(id: number) {
    return api.get<Order>(`/commandes/orders/${id}`)
  },
  setStatus(id: number, status: OrderStatus) {
    return api.patch<Order>(`/commandes/orders/${id}/status`, { status })
  },
  cancel(id: number) {
    return api.post<Order>(`/commandes/orders/${id}/cancel`)
  },
}

export const notificationsApi = {
  list(page = 1) {
    return api.get<{ items: NotificationRow[]; total: number; page: number; page_size: number }>(
      '/notifications/notifications',
      { params: { page } },
    )
  },
}
