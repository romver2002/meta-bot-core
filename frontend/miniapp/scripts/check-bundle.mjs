import { readFile } from 'node:fs/promises'
import { extname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { gzipSync } from 'node:zlib'

const KIB = 1024
const DIST_DIR = fileURLToPath(new URL('../dist/', import.meta.url))
const BUDGETS = new Map([
  ['.js', 64 * KIB],
  ['.css', 16 * KIB],
  ['.html', 8 * KIB],
])

const totals = new Map([...BUDGETS.keys()].map((extension) => [extension, 0]))
const html = await readFile(join(DIST_DIR, 'index.html'))
totals.set('.html', gzipSync(html).byteLength)

// Бюджет измеряет initial payload из актуального index.html и не считает
// оставшиеся на локальном диске хешированные assets прошлых сборок.
const assetReferences = [...html.toString().matchAll(/(?:src|href)="([^"?#]+\.(?:js|css))"/g)]
  .map((match) => match[1])
  .filter((path) => path !== undefined && !path.startsWith('http'))

for (const reference of new Set(assetReferences)) {
  const path = join(DIST_DIR, reference.replace(/^\.?\//, ''))
  const extension = extname(path)
  const compressedBytes = gzipSync(await readFile(path)).byteLength
  totals.set(extension, (totals.get(extension) ?? 0) + compressedBytes)
}

let failed = false
for (const [extension, budget] of BUDGETS) {
  const actual = totals.get(extension) ?? 0
  const summary = `${extension.slice(1).toUpperCase()}: ${(actual / KIB).toFixed(2)} / ${budget / KIB} KiB gzip`
  if (actual > budget) {
    console.error(`Bundle budget exceeded — ${summary}`)
    failed = true
  } else {
    console.log(`Bundle budget OK — ${summary}`)
  }
}

if (failed) process.exitCode = 1
