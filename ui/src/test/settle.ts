import { act } from '@testing-library/react'

/**
 * Give anything a click started a turn of the event loop.
 *
 * react-query's `mutate` does not call the mutation function synchronously, so
 * `expect(api.delete).not.toHaveBeenCalled()` written immediately after a click
 * passes whether the guard held or not - the request simply had not been made
 * yet when the assertion ran. Every "this must not happen" assertion that
 * follows a user action has to wait first, or it asserts nothing at all.
 *
 * Verified by mutation: with this in place, removing the confirm() from the
 * user-delete button fails the test that says the deletion was declined.
 * Without it, that test passed against the broken code.
 */
export async function settle(): Promise<void> {
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}
