import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Product } from '../api/types'

export interface CartLine {
  product: Product
  quantity: number
}

interface CartState {
  lines: CartLine[]
  add: (product: Product, quantity?: number) => string | null
  setQuantity: (productId: number, quantity: number) => void
  remove: (productId: number) => void
  clear: () => void
  total: number
  count: number
}

const CartContext = createContext<CartState | null>(null)
const KEY = 'marcheci_cart'

function load(): CartLine[] {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(
      (l): l is CartLine =>
        typeof l === 'object' && l !== null &&
        'product' in (l as CartLine) && 'quantity' in (l as CartLine),
    )
  } catch {
    return []
  }
}

export function CartProvider({ children }: { children: ReactNode }) {
  const [lines, setLines] = useState<CartLine[]>(load)

  useEffect(() => { localStorage.setItem(KEY, JSON.stringify(lines)) }, [lines])

  const add = useCallback((product: Product, quantity = 1): string | null => {
    if (product.stock <= 0) return 'Produit momentanément indisponible'
    const existing = lines.find((line) => line.product.id === product.id)
    const requestedQuantity = (existing?.quantity ?? 0) + quantity
    if (requestedQuantity > product.stock) {
      if (existing) {
        setLines((previous) => previous.map((line) => line.product.id === product.id
          ? { ...line, quantity: Math.min(product.stock, line.quantity) }
          : line))
      }
      return `Stock insuffisant : ${product.stock} maximum`
    }
    setLines((prev) => {
      const line = prev.find((item) => item.product.id === product.id)
      const target = (line?.quantity ?? 0) + quantity
      if (target > product.stock) {
        return line
          ? prev.map((item) => item.product.id === product.id ? { ...item, quantity: product.stock } : item)
          : prev
      }
      if (line) return prev.map((item) => item.product.id === product.id ? { ...item, quantity: target } : item)
      return [...prev, { product, quantity: target }]
    })
    return null
  }, [lines])

  const setQuantity = useCallback((productId: number, quantity: number) => {
    setLines((prev) =>
      prev.flatMap((l) => {
        if (l.product.id !== productId) return [l]
        if (quantity <= 0) return []
        if (quantity > l.product.stock) return [l] // garde la dernière valeur valide
        return [{ ...l, quantity }]
      }),
    )
  }, [])

  const remove = useCallback((productId: number) => {
    setLines((prev) => prev.filter((l) => l.product.id !== productId))
  }, [])

  const clear = useCallback(() => setLines([]), [])

  const total = useMemo(() => lines.reduce((sum, l) => sum + l.product.price_xof * l.quantity, 0), [lines])
  const count = useMemo(() => lines.reduce((sum, l) => sum + l.quantity, 0), [lines])

  return (
    <CartContext.Provider
      value={{ lines, add, setQuantity, remove, clear, total, count }}
    >
      {children}
    </CartContext.Provider>
  )
}

// oxlint-disable-next-line react/only-export-components
export function useCart(): CartState {
  const ctx = useContext(CartContext)
  if (!ctx) throw new Error('useCart hors CartProvider')
  return ctx
}
