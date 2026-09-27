import { useEffect, useId, useRef, useState } from 'react'
import { ClubCrest } from './ClubCrest'

interface Props {
  label: string
  teams: string[]
  value: string
  onChange: (team: string) => void
  disabledTeam?: string
  align?: 'left' | 'right'
}

/**
 * Crest-aware dropdown (a native <select> can't render images in options).
 * Implements the WAI-ARIA listbox pattern: arrows move, Enter selects,
 * Escape / click-outside closes, focus returns to the trigger.
 */
export function TeamPicker({ label, teams, value, onChange, disabledTeam, align = 'left' }: Props) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(Math.max(0, teams.indexOf(value)))
  const rootRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const listRef = useRef<HTMLUListElement>(null)
  const listId = useId()

  useEffect(() => {
    if (!open) return
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    listRef.current?.focus()
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [open])

  useEffect(() => {
    listRef.current?.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const select = (team: string) => {
    if (team === disabledTeam) return
    onChange(team)
    setOpen(false)
    buttonRef.current?.focus()
  }

  const move = (delta: number) => {
    let i = active
    for (let step = 0; step < teams.length; step++) {
      i = (i + delta + teams.length) % teams.length
      if (teams[i] !== disabledTeam) break
    }
    setActive(i)
  }

  const onListKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') (e.preventDefault(), move(1))
    else if (e.key === 'ArrowUp') (e.preventDefault(), move(-1))
    else if (e.key === 'Home') (e.preventDefault(), setActive(0))
    else if (e.key === 'End') (e.preventDefault(), setActive(teams.length - 1))
    else if (e.key === 'Enter' || e.key === ' ') (e.preventDefault(), select(teams[active]))
    else if (e.key === 'Escape' || e.key === 'Tab') {
      setOpen(false)
      buttonRef.current?.focus()
    }
  }

  return (
    <div className={`team-picker team-picker-${align}`} ref={rootRef}>
      <span className="eyebrow">{label}</span>
      <button
        ref={buttonRef}
        type="button"
        className="team-picker-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => {
          setActive(Math.max(0, teams.indexOf(value)))
          setOpen((o) => !o)
        }}
      >
        <span className="team-picker-name">{value}</span>
        <svg className="chevron" width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M6 9l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <ul
          ref={listRef}
          id={listId}
          role="listbox"
          tabIndex={-1}
          aria-label={label}
          aria-activedescendant={`${listId}-${active}`}
          className="team-picker-list"
          onKeyDown={onListKey}
        >
          {teams.map((team, i) => (
            <li
              key={team}
              id={`${listId}-${i}`}
              data-index={i}
              role="option"
              aria-selected={team === value}
              aria-disabled={team === disabledTeam}
              className={`team-picker-option${i === active ? ' is-active' : ''}${team === value ? ' is-selected' : ''}`}
              onMouseEnter={() => team !== disabledTeam && setActive(i)}
              onClick={() => select(team)}
            >
              <ClubCrest team={team} size={22} />
              <span>{team}</span>
              {team === value && (
                <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true" className="check">
                  <path d="M5 12l5 5 9-10" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
                </svg>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
