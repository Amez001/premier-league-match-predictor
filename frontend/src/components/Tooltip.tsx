import { createContext, useCallback, useContext, useEffect, useReducer, useState, type ReactNode } from 'react'

interface TooltipState {
  content: ReactNode
  anchor: Element
}

interface TooltipApi {
  show: (content: ReactNode, target: Element) => void
  hide: () => void
}

const TooltipContext = createContext<TooltipApi>({ show: () => {}, hide: () => {} })

/**
 * One shared tooltip for every chart. Anchored to the hovered/focused mark
 * itself (not the cursor), so keyboard focus shows exactly the same thing as
 * mouse hover. Tooltips only ever *enhance*: every value is also reachable
 * through a direct label or a table.
 */
export function TooltipProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<TooltipState | null>(null)
  const [, reposition] = useReducer((n: number) => n + 1, 0)

  const show = useCallback((content: ReactNode, anchor: Element) => setState({ content, anchor }), [])
  const hide = useCallback(() => setState(null), [])

  useEffect(() => {
    if (!state) return
    // Follow the anchor while the page scrolls (tabbing to an off-screen
    // mark scrolls it into view - hiding on scroll would break keyboard use),
    // and close if the anchor is gone: a mark that unmounts while hovered or
    // focused (e.g. on a page change) never fires mouseleave/blur.
    const onMove = () => (state.anchor.isConnected ? reposition() : hide())
    window.addEventListener('scroll', onMove, { capture: true, passive: true })
    window.addEventListener('resize', onMove)
    window.addEventListener('hashchange', hide)
    return () => {
      window.removeEventListener('scroll', onMove, { capture: true })
      window.removeEventListener('resize', onMove)
      window.removeEventListener('hashchange', hide)
    }
  }, [state, hide])

  const rect = state?.anchor.isConnected ? state.anchor.getBoundingClientRect() : null

  return (
    <TooltipContext.Provider value={{ show, hide }}>
      {children}
      {state && rect && (
        <div className="tooltip" role="tooltip" style={{ left: rect.left + rect.width / 2, top: rect.top }}>
          {state.content}
        </div>
      )}
    </TooltipContext.Provider>
  )
}

/** Spread onto any mark: hover + focus show the tooltip, leave/blur hide it. */
export function useTooltip(content: ReactNode) {
  const { show, hide } = useContext(TooltipContext)
  return {
    onMouseEnter: (e: React.MouseEvent) => show(content, e.currentTarget),
    onMouseLeave: hide,
    onFocus: (e: React.FocusEvent) => show(content, e.currentTarget),
    onBlur: hide,
  }
}
