import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { basename, isAbsolute } from 'node:path'

/**
 * Reads reviewed-advisories.json next to this script: an object that maps a package name to the
 * advisory URLs reviewed and judged not to apply to Bud. Returns a Map of package name to a Set of
 * those URLs; an advisory that is not listed fails the audit.
 */
function loadReviewedAdvisories() {
  const entries = JSON.parse(readFileSync(new URL('./reviewed-advisories.json', import.meta.url), 'utf8'))
  const valid =
    entries !== null &&
    typeof entries === 'object' &&
    !Array.isArray(entries) &&
    Object.values(entries).every((urls) => Array.isArray(urls) && urls.every((url) => typeof url === 'string'))
  if (!valid) {
    console.error('reviewed-advisories.json must map each package name to a list of advisory URLs.')
    process.exit(1)
  }
  return new Map(Object.entries(entries).map(([name, urls]) => [name, new Set(urls)]))
}

/**
 * Returns the absolute path of the npm CLI script that npm exposes as npm_execpath when it runs
 * `npm run audit`, and exits with an error when the audit is started any other way.
 */
function npmCliPath() {
  const npmCli = process.env.npm_execpath
  if (!npmCli || !isAbsolute(npmCli) || !/^npm-cli\.c?js$/.test(basename(npmCli))) {
    console.error('Start this audit with `npm run audit`: npm_execpath does not name the npm CLI script.')
    process.exit(1)
  }
  return npmCli
}

const reviewedAdvisories = loadReviewedAdvisories()

const result = spawnSync(process.execPath, [npmCliPath(), 'audit', '--json'], {
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
    : `npm audit found only reviewed non-applicable advisories (${reviewed.join(', ')}).`,
)
