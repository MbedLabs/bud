import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { productsApi } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { can, canManageAccess } from '../lib/access'
import AccessDenied from '../components/AccessDenied'
import ProductMembers from '../components/ProductMembers'

/** One product: its name, status and description, and the people holding each group on it. */
export default function ProductDetail() {
  const { id } = useParams<{ id: string }>()
  const productId = Number(id)
  const { user } = useAuth()
  const canView = can(user, 'products.view')
  const { data: product, isLoading, error } = useQuery({
    queryKey: ['product', productId],
    queryFn: () => productsApi.get(productId),
    enabled: canView && Number.isInteger(productId),
  })

  if (!canView) return <AccessDenied what="Products" />
  if (isLoading) return <p className="text-sm text-muted-foreground">Loading product...</p>
  if (error || !product) return <p role="alert" className="text-sm text-destructive">Could not load the product.</p>

  return (
    <div className="space-y-6 animate-fade-in">
      <div>
        <Link to="/products" className="text-sm text-muted-foreground hover:text-primary">&larr; Products</Link>
        <h2 className="mt-2 text-xl font-bold text-foreground">{product.name}</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          {product.status} · ID <span className="font-mono">{product.id}</span>
          {product.description ? ` · ${product.description}` : ''}
        </p>
      </div>
      {canManageAccess(user) ? (
        <ProductMembers productId={product.id} />
      ) : (
        <p className="text-sm text-muted-foreground">Access management is required to see and change the members of this product.</p>
      )}
    </div>
  )
}
