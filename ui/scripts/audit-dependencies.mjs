import { spawnSync } from 'node:child_process'

// Advisories reviewed and judged not to apply to this application, as
// `package name -> set of advisory URLs`. Anything not listed here fails the
// audit. Keep entries narrow (a specific advisory, never a whole package) and
// record why the advisory cannot affect Bud.
//
// Currently empty: GHSA-qwww-vcr4-c8h2 (React Router RSC) was the last entry and
// is fixed by React Router 8.
const reviewedAdvisories = new Map()

const result = spawnSync('npm', ['audit', '--json'], {
  encoding: 'utf8',
  maxBuffer: 20 * 1024 * 1024,
})

if (result.error) {
  console.error(`Unable to run npm audit: ${result.error.message}`)
  process.exit(1)
}

let report
try {
  report = JSON.parse(result.stdout)
} catch {
  console.error(result.stderr || result.stdout || 'npm audit returned invalid JSON')
  process.exit(1)
}

const vulnerabilities = report.vulnerabilities ?? {}
const memo = new Map()

function isReviewed(name, visiting = new Set()) {
  if (memo.has(name)) return memo.get(name)
  if (visiting.has(name)) return false

  const vulnerability = vulnerabilities[name]
  if (!vulnerability?.via?.length) return false

  const nextVisiting = new Set(visiting).add(name)
  const reviewed = vulnerability.via.every((via) => {
    if (typeof via === 'string') return isReviewed(via, nextVisiting)
    return reviewedAdvisories.get(name)?.has(via.url) ?? false
  })

  memo.set(name, reviewed)
  return reviewed
}

const unexpected = Object.keys(vulnerabilities).filter((name) => !isReviewed(name))
if (unexpected.length > 0) {
  const details = Object.fromEntries(unexpected.map((name) => [name, vulnerabilities[name]]))
  console.error('npm audit found unreviewed vulnerabilities:')
  console.error(JSON.stringify(details, null, 2))
  process.exit(1)
}

if (result.status !== 0 && Object.keys(vulnerabilities).length === 0) {
  console.error(result.stderr || 'npm audit failed without a vulnerability report')
  process.exit(1)
}

const reviewed = Object.keys(vulnerabilities)
console.log(
  reviewed.length === 0
    ? 'npm audit found no vulnerabilities.'
    : `npm audit found only the reviewed non-applicable RSC advisory (${reviewed.join(', ')}).`,
)
