// Same letters as the table's G / N / P columns (gagné, nul, perdu).
const LABEL = { W: 'G', D: 'N', L: 'P' } as const
const WORD = { W: 'victoire', D: 'nul', L: 'défaite' } as const

/**
 * Last five results, oldest to newest. Result is a status (good / neutral /
 * bad), so it uses status colors - always with the letter inside, never
 * color alone.
 */
export function FormGuide({ form }: { form: ('W' | 'D' | 'L')[] }) {
  return (
    <span className="form" aria-label={`Forme, du plus ancien au plus récent : ${form.map((r) => WORD[r]).join(', ')}`}>
      {form.map((r, i) => (
        <span key={i} className={`form-chip form-${r}`} aria-hidden="true">
          {LABEL[r]}
        </span>
      ))}
    </span>
  )
}
