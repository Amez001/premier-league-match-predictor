import { useState } from 'react'
import { clubColor, clubInitials, clubSlug } from '../data/clubColors'

interface Props {
  team: string
  size?: number
}

/**
 * Real club crest when scripts/download_club_crests.py has fetched one for
 * this team (best-effort, not committed to the repo - see README). Falls
 * back to a colored monogram so a missing/failed crest never shows a broken
 * image icon.
 */
export function ClubCrest({ team, size = 32 }: Props) {
  const [failed, setFailed] = useState(false)
  const slug = clubSlug(team)

  if (failed) {
    return (
      <div
        className="club-crest club-crest-fallback"
        style={{ width: size, height: size, background: clubColor(team) }}
        title={team}
      >
        {clubInitials(team)}
      </div>
    )
  }

  return (
    <img
      className="club-crest"
      src={`/crests/${slug}.png`}
      onError={() => setFailed(true)}
      alt={`${team} crest`}
      width={size}
      height={size}
    />
  )
}
