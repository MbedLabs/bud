import { authApi } from '../api/client'
import TokenConfirmation from '../components/TokenConfirmation'

export default function ConfirmEmailChange() {
  return (
    <TokenConfirmation
      title="Confirm Email Change"
      subtitle="Confirming your new email address for Bud TMP."
      pendingText="Confirming your new email address..."
      missingTokenText="Missing confirmation token"
      failureText="Email change confirmation failed"
      confirm={authApi.confirmEmailChange}
    />
  )
}
