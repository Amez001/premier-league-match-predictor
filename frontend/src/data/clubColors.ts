// Public-domain style reference: each club's well-known primary shirt color,
// used only as a UI accent (not a claim on the club's branding). Keyed by
// the football-data.co.uk team name used everywhere else in this project.
export const CLUB_COLORS: Record<string, string> = {
  Arsenal: '#EF0107',
  'Aston Villa': '#670E36',
  Bournemouth: '#DA291C',
  Brentford: '#E30613',
  Brighton: '#0057B8',
  Burnley: '#6C1D45',
  Chelsea: '#034694',
  'Crystal Palace': '#1B458F',
  Everton: '#003399',
  Fulham: '#CC0000',
  Leeds: '#FFCD00',
  Liverpool: '#C8102E',
  'Man City': '#6CABDD',
  'Man United': '#DA291C',
  Newcastle: '#241F20',
  'Nottm Forest': '#DD0000',
  Sunderland: '#EB172B',
  Tottenham: '#132257',
  'West Ham': '#7A263A',
  Wolves: '#FDB913',
}

const FALLBACK_COLOR = '#38003C' // Premier League purple

export function clubColor(team: string): string {
  return CLUB_COLORS[team] ?? FALLBACK_COLOR
}

// Must match the slugify logic in scripts/download_club_crests.py so
// <ClubCrest> can find the file that script downloads.
export function clubSlug(team: string): string {
  return team
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

export function clubInitials(team: string): string {
  const words = team.split(/\s+/).filter(Boolean)
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase()
  return words.map((w) => w[0]).join('').slice(0, 3).toUpperCase()
}
