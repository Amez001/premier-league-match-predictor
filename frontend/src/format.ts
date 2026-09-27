const pctFmt = new Intl.NumberFormat('fr-FR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 })
const pct0Fmt = new Intl.NumberFormat('fr-FR', { style: 'percent', maximumFractionDigits: 0 })
const num1Fmt = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const num2Fmt = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
const intFmt = new Intl.NumberFormat('fr-FR')
const dateFmt = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })

/** "62,3 %" - with "<0,1 %" for tiny-but-nonzero odds and "—" for exactly zero, so a 0.03% long shot never reads as impossible. */
export function pct(p: number): string {
  if (p === 0) return '—'
  if (p < 0.001) return '<0,1 %'
  if (p > 0.999 && p < 1) return '>99,9 %'
  return pctFmt.format(p)
}

export const pct0 = (p: number) => pct0Fmt.format(p)
export const num1 = (x: number) => num1Fmt.format(x)
export const num2 = (x: number) => num2Fmt.format(x)
export const int = (x: number) => intFmt.format(x)
export const signed = (x: number) => (x > 0 ? '+' : x < 0 ? '−' : '') + intFmt.format(Math.abs(Math.round(x)))
/**
 * "20 septembre 2026" from "2026-09-20". Parsed as a *local* date on purpose:
 * `new Date("2026-09-20")` means midnight UTC, which is still Sept 19 in
 * any timezone west of Greenwich (e.g. Toronto) - off by one day.
 */
export function longDate(iso: string): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return dateFmt.format(new Date(y, m - 1, d))
}
