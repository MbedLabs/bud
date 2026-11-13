const PRODUCT_RESOURCES = ['evidence', 'reports', 'custom_runs', 'bloom_publish']

/** Whether the permission counts per product. */
export function isProductScoped(permission: string): boolean {
  return PRODUCT_RESOURCES.includes(permission.split('.')[0]) || permission === 'products.manage'
}

/** Whether the permission counts app-wide. */
export function isAppScoped(permission: string): boolean {
  return !PRODUCT_RESOURCES.includes(permission.split('.')[0])
}

/** Whether a group gives anything per product. */
export function givesProductAccess(group: { permissions: string[] }): boolean {
  return group.permissions.some(isProductScoped)
}

/** Whether a group gives anything app-wide. */
export function givesAppAccess(group: { permissions: string[] }): boolean {
  return group.permissions.some(isAppScoped)
}
