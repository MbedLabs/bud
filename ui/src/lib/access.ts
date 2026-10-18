import type { User } from '../api/client'

/** Whether the signed-in user holds `resource.action`; Admin holds everything. */
export function can(user: Pick<User, 'role' | 'permissions'> | null | undefined, permission: string): boolean {
  if (!user) return false
  if (user.role === 'admin') return true
  return user.permissions?.includes(permission) ?? false
}

/** Who sees the Access page: Admins and holders of access management. */
export function canManageAccess(user: Pick<User, 'role' | 'permissions'> | null | undefined): boolean {
  return can(user, 'access.manage')
}

export const RESOURCE_LABELS: Record<string, string> = {
  evidence: 'Runs, results and artifacts',
  reports: 'Reports',
  products: 'Products',
  stations: 'Test Stations',
  custom_runs: 'Custom runs',
  bloom_publish: 'Reports publishing',
  settings: 'Settings and integrations',
  audit: 'Audit log',
  access: 'Access',
}

export const ACTION_LABELS: Record<string, string> = {
  view: 'Read',
  export: 'Read',
  manage: 'Write',
  create: 'Write',
  execute: 'Write',
  edit: 'Write',
}

/** A stored permission's resource and displayed Read or Write operation. */
export function permissionLabel(permission: string): string {
  const [resource, action] = permission.split('.')
  return `${RESOURCE_LABELS[resource] ?? resource}: ${ACTION_LABELS[action] ?? action}`
}
