#!/usr/bin/env node
/**
 * Generates TypeScript types from contracts/schemas/*.schema.json into
 * src/contracts/generated/.
 *
 * Must be run from the web-phone/ directory (npm run contracts does this).
 * The tool requires CWD=contracts/schemas/ so that $ref relative paths resolve.
 */
import { execSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dir = dirname(fileURLToPath(import.meta.url))
const schemasDir = resolve(__dir, '../../contracts/schemas')
const outDir = resolve(__dir, '../src/contracts/generated')
const bin = resolve(__dir, '../node_modules/.bin/json2ts')

mkdirSync(outDir, { recursive: true })

const schemas = [
  'attendee',
  'claim',
  'event',
  'flag',
  'profile-facts',
  'profile',
  'session',
  'user',
  'utterance',
  'voice-calibration',
  'ws-envelope',
  'ws-events',
]

for (const name of schemas) {
  const input = `${name}.schema.json`
  const output = resolve(outDir, `${name}.ts`)
  try {
    execSync(`"${bin}" -i "${input}" -o "${output}"`, { cwd: schemasDir, stdio: 'pipe' })
    console.log(`generated: ${name}.ts`)
  } catch (err) {
    console.error(`failed: ${name}`)
    console.error(err.stderr?.toString() ?? err.message)
    process.exit(1)
  }
}

console.log('contracts generated successfully')
