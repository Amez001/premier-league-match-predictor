import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useMemo } from 'react'

/** Renders a LaTeX formula with KaTeX (display = centered block). */
export function Tex({ children, display = false }: { children: string; display?: boolean }) {
  const html = useMemo(
    () => katex.renderToString(children, { displayMode: display, throwOnError: false, output: 'html' }),
    [children, display],
  )
  return <span className={display ? 'tex-display' : 'tex-inline'} dangerouslySetInnerHTML={{ __html: html }} />
}
