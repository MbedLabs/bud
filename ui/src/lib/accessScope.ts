const PRODUCT_RESOURCES = new Set(['evidence', 'reports', 'custom_runs', 'bloom_publish'])

/** Whether the permission counts per product. */
export function isProductScoped(permission: string): boolean {
  return PRODUCT_RESOURCES.has(permission.split('.')[0]) || permission === 'products.manage'
}

/** Whether the permission counts app-wide. */
export function isAppScoped(permission: string): boolean {
  return !PRODUCT_RESOURCES.has(permission.split('.')[0])
}

/** Whether a group gives anything per product. */
export function givesProductAccess(group: { permissions: string[] }): boolean {
  return group.permissions.some(isProductScoped)
}

/** Whether a policy gives anything app-wide. */
export function isApplicationPolicy(policy: { permissions: Record<string, string[]> }): boolean {
  return Object.entries(policy.permissions).some(([resource, actions]) => actions.some((action) => isAppScoped(`${resource}.${action}`)))
}
