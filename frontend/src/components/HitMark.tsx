/** Hit / miss mark: status color *and* a check or cross, never color alone. */
export function HitMark({ hit }: { hit: boolean }) {
  return (
    <span className={`hit-mark ${hit ? 'is-hit' : 'is-miss'}`} role="img" aria-label={hit ? 'réussi' : 'raté'}>
      <svg width="10" height="10" viewBox="0 0 12 12" aria-hidden="true">
        {hit ? (
          <path d="M2.5 6.5l2.3 2.3 4.7-5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        ) : (
          <path d="M3 3l6 6M9 3l-6 6" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        )}
      </svg>
    </span>
  )
}
