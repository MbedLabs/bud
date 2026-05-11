import '@testing-library/jest-dom/vitest'
import { beforeEach, vi } from 'vitest'

function createMemoryStorage(): Storage {
  const memoryStore = new Map<string, string>()
  return {
    get length(): number {
      return memoryStore.size
    },
    clear(): void {
      memoryStore.clear()
    },
    getItem(key: string): string | null {
      return memoryStore.has(key) ? memoryStore.get(key)! : null
    },
    key(index: number): string | null {
      return [...memoryStore.keys()][index] ?? null
    },
    removeItem(key: string): void {
      memoryStore.delete(key)
    },
    setItem(key: string, value: string): void {
      memoryStore.set(key, value)
    },
  }
}

beforeEach(() => {
  const localStub = createMemoryStorage()
  vi.stubGlobal('localStorage', localStub)

  if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'localStorage', {
      value: localStub,
      writable: true,
      configurable: true,
    })
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      configurable: true,
      value: vi.fn((query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: (): void => undefined,
        removeListener: (): void => undefined,
        addEventListener: (): void => undefined,
        removeEventListener: (): void => undefined,
        dispatchEvent: (): boolean => false,
      })),
    })
  }
})
