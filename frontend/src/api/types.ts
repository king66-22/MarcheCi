/** Types alignés sur les schémas Pydantic des microservices. */

export interface ProductImage {
  id: number
  url: string
  position: number
}

export interface Product {
  id: number
  slug: string
  name: string
  description: string
  price_xof: number
  category_id: number | null
  owner_id: number | null
  stock: number
  image_url: string | null
  is_active: boolean
  /** Présent sur le détail produit uniquement (galerie ordonnée). */
  images?: ProductImage[]
}

export interface Category {
  id: number
  slug: string
  name: string
  product_count?: number
}

export interface ProductPage {
  items: Product[]
  total: number
  page: number
  page_size: number
}

export interface OrderItem {
  product_id: number
  product_name: string
  unit_price_xof: number
  quantity: number
}

export interface Order {
  id: number
  user_id: number
  status: OrderStatus
  total_xof: number
  delivery_address: string
  delivery_phone: string
  payment_status: string
  created_at: string
  items: OrderItem[]
}

export type OrderStatus =
  | 'EN_ATTENTE' | 'CONFIRMEE' | 'EN_PREPARATION' | 'EXPEDIEE' | 'LIVREE' | 'ANNULEE'

export interface OrderPage {
  items: Order[]
  total: number
  page: number
  page_size: number
}

export type Role = 'CLIENT' | 'COMMERCANT' | 'ADMIN'

export interface User {
  id: number
  email: string
  full_name: string
  phone: string | null
  role: Role
  created_at?: string
  is_active?: boolean
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  role: Role
}

export interface NotificationRow {
  id: number
  order_id: number | null
  user_id: number | null
  channel: string
  recipient: string
  template: string
  status: string
  attempts: number
  created_at: string
}

/** Montant FCFA : formatage standard ivoirien (internationales côté front, tout reste entier) */
export const fcfa = (n: number): string =>
  `${new Intl.NumberFormat('fr-FR').format(n)} FCFA`
