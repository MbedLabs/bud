import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { Archive, ArchiveRestore, Check, Copy, Package, Pencil, Plus, Trash2 } from 'lucide-react'
import { extractApiErrorMessage, productsApi } from '../api/client'
import type { Product, ProductStatus } from '../api/client'
import { useAuth } from '../contexts/AuthContext'
import { can } from '../lib/access'
import {
  productDeleteConfirmationMatches,
  productDeleteConfirmationPhrase,
} from '../lib/productDelete'
import AccessDenied from '../components/AccessDenied'
import ConfirmDialog from '../components/ConfirmDialog'
import { useEscapeKey } from '../hooks/useEscapeKey'

const MAX_NAME_LENGTH = 255

interface ProductForm {
  product: Product | null
  name: string
  description: string
}

const DIALOG_BACKDROP = 'fixed inset-0 bg-black/50 backdrop-blur-xs flex items-center justify-center z-50'
const DIALOG_CARD = 'relative m-0 bg-card rounded-lg shadow-elegant p-6 max-w-sm w-full mx-4 text-foreground'
const DIALOG_ERROR = 'mb-4 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-sm text-destructive'
const FIELD = 'w-full px-3 py-2 bg-background border border-input rounded-lg text-sm text-foreground'
const CANCEL_BUTTON = 'px-4 py-2 border border-input rounded-md text-foreground hover:bg-accent/50 text-sm'
const ICON_BUTTON = 'p-1.5 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors'

/** A product's status as a badge. */
function StatusBadge({ status }: Readonly<{ status: ProductStatus }>) {
  const colours =
    status === 'Active'
      ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400'
      : 'bg-muted text-muted-foreground'
  return <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${colours}`}>{status}</span>
}

/** The message shown in place of the table while it loads, fails or is empty. */
function tableMessage(isLoading: boolean, failed: boolean, count: number): string | null {
  if (isLoading) return 'Loading products...'
  if (failed) return 'Could not load the products.'
  if (count === 0) return 'No products yet.'
  return null
}

/**
 * The Products page: the products a run can belong to, each with the ID the runner sends.
 * Users with products.manage add, edit, archive, restore and delete them.
 */
export default function Products() {
  const { user } = useAuth()
  const canView = can(user, 'products.view')
  const canManage = can(user, 'products.manage')
  const queryClient = useQueryClient()

  const [form, setForm] = useState<ProductForm | null>(null)
  const [archiving, setArchiving] = useState<Product | null>(null)
  const [deleting, setDeleting] = useState<Product | null>(null)
  const [deleteText, setDeleteText] = useState('')
  const [actionError, setActionError] = useState('')
  const [copiedId, setCopiedId] = useState<number | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['products'],
    queryFn: productsApi.list,
    enabled: canView,
  })

  const refresh = () => {
    setActionError('')
    void queryClient.invalidateQueries({ queryKey: ['products'] })
  }

  const closeForm = () => {
    setForm(null)
    setActionError('')
  }

  const closeDelete = () => {
    setDeleting(null)
    setDeleteText('')
    setActionError('')
  }

  const saveProduct = useMutation({
    mutationFn: ({ product, name, description }: ProductForm) => {
      const body = { name: name.trim(), description: description.trim() || null }
      return product ? productsApi.update(product.id, body) : productsApi.create(body)
    },
    onSuccess: () => {
      setForm(null)
      refresh()
    },
    onError: (failure) => setActionError(extractApiErrorMessage(failure, 'Could not save the product')),
  })

  const changeStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: ProductStatus }) =>
      productsApi.update(id, { status }),
    onSuccess: () => {
      setArchiving(null)
      refresh()
    },
    onError: (failure) =>
      setActionError(extractApiErrorMessage(failure, 'Could not change the product status')),
  })

  const removeProduct = useMutation({
    mutationFn: productsApi.remove,
    onSuccess: () => {
      setDeleting(null)
      setDeleteText('')
      refresh()
    },
    onError: (failure) => setActionError(extractApiErrorMessage(failure, 'Could not delete the product')),
  })

  useEscapeKey(closeForm, form !== null)
  useEscapeKey(closeDelete, deleting !== null)

  if (!canView) return <AccessDenied what="Products" />

  const products = data || []
  const message = tableMessage(isLoading, Boolean(error), products.length)
  const deletePhrase = deleting ? productDeleteConfirmationPhrase(deleting.name) : ''
  const deleteMatches = productDeleteConfirmationMatches(deleteText, deletePhrase)
  const formNameValid = form !== null && form.name.trim().length > 0

  const copyId = async (id: number) => {
    try {
      await navigator.clipboard.writeText(String(id))
      setCopiedId(id)
      window.setTimeout(() => setCopiedId(null), 2000)
    } catch {
      setCopiedId(null)
    }
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap justify-between items-center gap-3">
        <p className="text-sm text-muted-foreground">
          A product&apos;s ID is the value of <span className="font-mono">productId</span> for the runner.
        </p>
        {canManage && (
          <button
            type="button"
            onClick={() => {
              setActionError('')
              setForm({ product: null, name: '', description: '' })
            }}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-gradient-button text-white rounded-lg hover:opacity-90 transition-opacity text-sm"
          >
            <Plus className="h-4 w-4" />
            New product
          </button>
        )}
      </div>

      {actionError && !form && !archiving && !deleting && (
        <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3 text-sm text-destructive">
          {actionError}
        </div>
      )}

      {message ? (
        <div className="bg-card border border-border rounded-xl p-8 text-center">
          <Package className="h-8 w-8 mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">{message}</p>
        </div>
      ) : (
        <div className="border border-border rounded-xl overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th className="text-left font-medium px-4 py-2">Name</th>
                <th className="text-left font-medium px-4 py-2">Description</th>
                <th className="text-left font-medium px-4 py-2">Status</th>
                <th className="text-left font-medium px-4 py-2">ID</th>
                {canManage && <th className="text-right font-medium px-4 py-2">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr key={product.id} className="border-t border-border align-top">
                  <td className="px-4 py-2 font-medium">
                    <Link to={`/products/${product.id}`} className="text-foreground hover:text-primary hover:underline">
                      {product.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{product.description || ''}</td>
                  <td className="px-4 py-2">
                    <StatusBadge status={product.status} />
                  </td>
                  <td className="px-4 py-2 whitespace-nowrap">
                    <span className="font-mono text-foreground">{product.id}</span>
                    <button
                      type="button"
                      onClick={() => void copyId(product.id)}
                      aria-label={`Copy the ID of ${product.name}`}
                      title="Copy ID"
                      className={`ml-1 align-middle ${ICON_BUTTON}`}
                    >
                      {copiedId === product.id ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                    </button>
                  </td>
                  {canManage && (
                    <td className="px-4 py-2 text-right whitespace-nowrap">
                      <button
                        type="button"
                        onClick={() => {
                          setActionError('')
                          setForm({ product, name: product.name, description: product.description || '' })
                        }}
                        aria-label={`Edit ${product.name}`}
                        title="Edit"
                        className={ICON_BUTTON}
                      >
                        <Pencil className="h-4 w-4" />
                      </button>
                      {product.status === 'Active' ? (
                        <button
                          type="button"
                          onClick={() => {
                            setActionError('')
                            setArchiving(product)
                          }}
                          aria-label={`Archive ${product.name}`}
                          title="Archive"
                          className={ICON_BUTTON}
                        >
                          <Archive className="h-4 w-4" />
                        </button>
                      ) : (
                        <button
                          type="button"
                          onClick={() => changeStatus.mutate({ id: product.id, status: 'Active' })}
                          disabled={changeStatus.isPending}
                          aria-label={`Restore ${product.name}`}
                          title="Restore"
                          className={ICON_BUTTON}
                        >
                          <ArchiveRestore className="h-4 w-4" />
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => {
                          setActionError('')
                          setDeleteText('')
                          setDeleting(product)
                        }}
                        aria-label={`Delete ${product.name}`}
                        title="Delete"
                        className={`${ICON_BUTTON} hover:text-destructive`}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {form && (
        <div className={DIALOG_BACKDROP}>
          <button
            type="button"
            aria-label="Close product dialog backdrop"
            tabIndex={-1}
            className="absolute inset-0 h-full w-full cursor-default"
            onClick={closeForm}
          />
          <dialog
            open
            aria-modal="true"
            aria-label={form.product ? 'Edit product' : 'New product'}
            className={DIALOG_CARD}
          >
            <form
              onSubmit={(event) => {
                event.preventDefault()
                if (formNameValid) saveProduct.mutate(form)
              }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-4">
                {form.product ? 'Edit product' : 'New product'}
              </h3>
              <label htmlFor="product-name" className="block text-xs font-medium text-muted-foreground mb-1.5">
                Name
              </label>
              <input
                id="product-name"
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
                maxLength={MAX_NAME_LENGTH}
                autoFocus
                className={`${FIELD} mb-4`}
              />
              <label htmlFor="product-description" className="block text-xs font-medium text-muted-foreground mb-1.5">
                Description
              </label>
              <textarea
                id="product-description"
                value={form.description}
                onChange={(event) => setForm({ ...form, description: event.target.value })}
                rows={3}
                className={`${FIELD} mb-4`}
              />
              {actionError && <div className={DIALOG_ERROR}>{actionError}</div>}
              <div className="flex justify-end gap-2">
                <button type="button" onClick={closeForm} className={CANCEL_BUTTON}>
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!formNameValid || saveProduct.isPending}
                  className="px-4 py-2 bg-gradient-button text-white rounded-md hover:opacity-90 disabled:opacity-50 text-sm"
                >
                  {saveProduct.isPending ? 'Saving...' : 'Save'}
                </button>
              </div>
            </form>
          </dialog>
        </div>
      )}

      {archiving && (
        <ConfirmDialog
          title="Archive this product?"
          body={`New runs and result uploads for ${archiving.name} are refused until it is restored. Its existing runs stay.`}
          confirmLabel="Archive"
          pendingLabel="Archiving..."
          isPending={changeStatus.isPending}
          error={actionError}
          onConfirm={() => changeStatus.mutate({ id: archiving.id, status: 'Archived' })}
          onCancel={() => {
            setArchiving(null)
            setActionError('')
          }}
        />
      )}

      {deleting && (
        <div className={DIALOG_BACKDROP}>
          <button
            type="button"
            aria-label="Close Delete product backdrop"
            tabIndex={-1}
            className="absolute inset-0 h-full w-full cursor-default"
            onClick={closeDelete}
          />
          <dialog open aria-modal="true" aria-label="Delete product" className={DIALOG_CARD}>
            <form
              onSubmit={(event) => {
                event.preventDefault()
                if (deleteMatches) removeProduct.mutate(deleting.id)
              }}
            >
              <h3 className="text-lg font-semibold text-foreground mb-2">Delete product?</h3>
              <p className="text-sm text-muted-foreground mb-4">
                {deleting.name} is deleted for good. Type{' '}
                <span className="font-mono text-foreground">{deletePhrase}</span> to confirm.
              </p>
              <input
                value={deleteText}
                onChange={(event) => setDeleteText(event.target.value)}
                aria-label="Delete confirmation"
                autoFocus
                className={`${FIELD} mb-4`}
              />
              {actionError && <div className={DIALOG_ERROR}>{actionError}</div>}
              <div className="flex justify-end gap-2">
                <button type="button" onClick={closeDelete} className={CANCEL_BUTTON}>
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!deleteMatches || removeProduct.isPending}
                  className="px-4 py-2 bg-destructive text-white rounded-md hover:bg-destructive/90 disabled:opacity-50 text-sm"
                >
                  {removeProduct.isPending ? 'Deleting...' : 'Delete'}
                </button>
              </div>
            </form>
          </dialog>
        </div>
      )}
    </div>
  )
}
