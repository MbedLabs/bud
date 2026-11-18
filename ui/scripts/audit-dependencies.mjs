import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { basename, isAbsolute } from 'node:path'

/** The longest a reviewed advisory may go before it must be reviewed again. */
const MAX_REVIEW_DAYS = 90
const DAY_MS = 24 * 60 * 60 * 1000
const today = new Date().toISOString().slice(0, 10)

/** Returns true for a JSON object that is neither null nor an array. */
function isPlainObject(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** Returns true for a non-empty string that is not only spaces. */
function isText(value) {
  return typeof value === 'string' && value.trim() !== ''
}

/** Returns true for a real calendar date written as YYYY-MM-DD. */
function isDate(value) {
  return (
    typeof value === 'string' &&
    /^\d{4}-\d{2}-\d{2}$/.test(value) &&
    !Number.isNaN(Date.parse(`${value}T00:00:00Z`)) &&
    new Date(`${value}T00:00:00Z`).toISOString().startsWith(value)
  )
}

/** Returns the number of days from today to the given YYYY-MM-DD date. */
function daysUntil(date) {
  return Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) / DAY_MS)
}

/**
 * Reads reviewed-advisories.json next to this script: an object that maps a package name to an object of
 * `advisory URL: review`, where the review holds the `reason` the advisory does not apply to Bud, the affected
 * `range` the advisory gave when it was reviewed, and the `review_by` date (YYYY-MM-DD, at most MAX_REVIEW_DAYS
 * ahead) by which it must be reviewed again. Returns a Map of package name to a Map of advisory URL to its review;
 * an advisory that is not listed fails the audit.
 */
function loadReviewedAdvisories() {
  const entries = JSON.parse(readFileSync(new URL('./reviewed-advisories.json', import.meta.url), 'utf8'))
  const valid =
    isPlainObject(entries) &&
    Object.values(entries).every(
      (reviews) =>
        isPlainObject(reviews) &&
        Object.entries(reviews).every(
          ([url, review]) =>
            url.startsWith('https://') &&
            isPlainObject(review) &&
            isText(review.reason) &&
            isText(review.range) &&
            isDate(review.review_by),
        ),
    )
  if (!valid) {
    console.error(
      'reviewed-advisories.json must map each package name to an object of advisory URL: { "reason", "range", "review_by": "YYYY-MM-DD" }.',
    )
    process.exit(1)
  }
  return new Map(Object.entries(entries).map(([name, reviews]) => [name, new Map(Object.entries(reviews))]))
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

/**
 * Returns true when every advisory the package leads to is listed in reviewed-advisories.json.
 * A package met again on its own dependency path counts as reviewed, and its advisories are judged where the path ends.
 */
function isReviewed(name, visiting = new Set()) {
  if (memo.has(name)) return memo.get(name)
  if (visiting.has(name)) return true

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

/** Returns a map of `package advisoryURL` to the affected range npm audit reports for it. */
function reportedRanges() {
  const ranges = new Map()
  for (const [name, vulnerability] of Object.entries(vulnerabilities)) {
    for (const via of vulnerability.via ?? []) {
      if (typeof via !== 'string') ranges.set(`${name} ${via.url}`, via.range)
    }
  }
  return ranges
}

/**
 * Returns the messages for one reviewed advisory: npm audit does not report it, reports it with a range other than
 * the reviewed one, or its review_by date has passed or lies more than MAX_REVIEW_DAYS ahead.
 */
function reviewProblem(label, review, reported) {
  const problems = []
  if (reported === undefined) {
    problems.push(`${label}: npm audit no longer reports it; remove it from reviewed-advisories.json.`)
  } else if (reported !== review.range) {
    problems.push(
      `${label}: the affected range is now "${reported}", reviewed for "${review.range}"; a fixed release may exist, upgrade or review it again.`,
    )
  }
  if (review.review_by < today) {
    problems.push(`${label}: its review expired on ${review.review_by}; review it again or fix it.`)
  } else if (daysUntil(review.review_by) > MAX_REVIEW_DAYS) {
    problems.push(`${label}: review_by ${review.review_by} is more than ${MAX_REVIEW_DAYS} days away.`)
  }
  return problems
}

/** Returns the messages for every reviewed advisory in reviewed-advisories.json. */
function reviewProblems() {
  const ranges = reportedRanges()
  return [...reviewedAdvisories].flatMap(([name, reviews]) =>
    [...reviews].flatMap(([url, review]) => reviewProblem(`${name} ${url}`, review, ranges.get(`${name} ${url}`))),
  )
}

const problems = reviewProblems()
if (problems.length > 0) {
  console.error('reviewed-advisories.json needs attention:')
  for (const problem of problems) console.error(`- ${problem}`)
  process.exit(1)
}

const reviewed = Object.keys(vulnerabilities)
console.log(
  reviewed.length === 0
    ? 'npm audit found no vulnerabilities.'
    : `npm audit found only reviewed non-applicable advisories (${reviewed.join(', ')}), each to be reviewed again by its review_by date.`,
)
