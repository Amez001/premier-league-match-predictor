import { ClubCrest } from './ClubCrest'

interface Props {
  label: string
  teams: string[]
  value: string
  onChange: (team: string) => void
  disabledTeam?: string
}

export function TeamSelect({ label, teams, value, onChange, disabledTeam }: Props) {
  return (
    <label className="team-select">
      <span className="team-select-label">{label}</span>
      <div className="team-select-control">
        <ClubCrest team={value} size={28} />
        <select value={value} onChange={(e) => onChange(e.target.value)}>
          {teams.map((team) => (
            <option key={team} value={team} disabled={team === disabledTeam}>
              {team}
            </option>
          ))}
        </select>
      </div>
    </label>
  )
}
