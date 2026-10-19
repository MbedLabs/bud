import { authApi } from '../api/client'
import TokenConfirmation from '../components/TokenConfirmation'

export default function VerifyEmail() {
  return (
    <TokenConfirmation
      title="Verify Email"
      subtitle="Confirming your email address for Bud TMP."
      pendingText="Verifying your email address..."
      missingTokenText="Missing verification token"
      failureText="Email verification failed"
      confirm={authApi.verifyEmail}
    />
  )
}
