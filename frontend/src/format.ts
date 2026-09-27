const pctFmt = new Intl.NumberFormat('fr-FR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const num1Fmt = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const num2Fmt = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const intFmt = new Intl.NumberFormat('fr-FR')
const dateFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
const shortDateFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'short' })

const NBSP = ' '

/**
 * French formatting uses a narrow no-break space (U+202F) as thousands
 * separator, which Archivo draws with almost no width ("10000" instead of
 * "10 000"). Swap it for a regular no-break space, like the one Intl already
 * puts before "%".
 */
const fixSpaces = (s: string) => s.replace(/ /g, NBSP)

/** "62,3 %" - with "<0,1 %" for tiny-but-nonzero odds and "—" for exactly zero, so a 0.03% long shot never reads as impossible. */
export function pct(p: number): string {
  if (p === 0) return '—'
  if (p < 0.001) return `<0,1${NBSP}%`
  if (p > 0.999 && p < 1) return `>99,9${NBSP}%`
  return fixSpaces(pctFmt.format(p))
}

export const num1 = (x: number) => fixSpaces(num1Fmt.format(x))
export const num2 = (x: number) => fixSpaces(num2Fmt.format(x))
export const int = (x: number) => fixSpaces(intFmt.format(x))
export const signed = (x: number) => (x > 0 ? '+' : x < 0 ? '−' : '') + int(Math.abs(Math.round(x)))

/**
 * Parsed as a *local* date on purpose: `new Date("2026-09-20")` means
 * midnight UTC, which is still Sept 19 in any timezone west of Greenwich
 * (e.g. Toronto) - off by one day.
 */
function localDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** "20 septembre 2026" */
export const longDate = (iso: string) => dateFmt.format(localDate(iso))
/** "20 sept." */
export const shortDate = (iso: string) => shortDateFmt.format(localDate(iso))
