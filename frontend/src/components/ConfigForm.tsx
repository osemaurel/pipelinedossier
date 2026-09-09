import { useEffect, useMemo, useState } from 'react'
import type { GenerationRequest, UploadResult } from '../api'

interface Props {
  upload: UploadResult
  busy: boolean
  onSubmit: (request: GenerationRequest) => void
}

const PRESETS = [10, 25, 50, 100, 250]

const ADVANCED_FIELDS: { key: string; label: string }[] = [
  { key: 'situation', label: 'Situation' },
  { key: 'niveau_etudes', label: "Niveau d'études" },
  { key: 'type_relation', label: 'Type de relation' },
  { key: 'enfants', label: 'Enfants' },
  { key: 'religion', label: 'Religion' },
  { key: 'prete_a_demenager', label: 'Prête à déménager' },
]

function TokenList({
  values,
  onChange,
  placeholder,
}: {
  values: string[]
  onChange: (next: string[]) => void
  placeholder: string
}) {
  const [draft, setDraft] = useState('')

  const add = () => {
    const value = draft.trim()
    if (value && !values.includes(value)) onChange([...values, value])
    setDraft('')
  }

  return (
    <div>
      <div className="flex gap-2">
        <input
          className="input"
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault()
              add()
            }
          }}
        />
        <button type="button" className="btn-secondary shrink-0" onClick={add}>
          Ajouter
        </button>
      </div>
      {values.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {values.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => onChange(values.filter((item) => item !== value))}
              className="chip border-ink-300 bg-white text-ink-700 hover:border-red-300 hover:text-red-700"
            >
              {value} ✕
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export function ConfigForm({ upload, busy, onSubmit }: Props) {
  const [profileCount, setProfileCount] = useState(50)
  const [autoAgents, setAutoAgents] = useState(false)
  const [agentCount, setAgentCount] = useState(5)
  const [avatars, setAvatars] = useState(3)
  const [countries, setCountries] = useState<string[]>(upload.default_countries.slice(0, 6))
  const [cities, setCities] = useState<string[]>([])
  const [professions, setProfessions] = useState<string[]>([])
  const [ageMin, setAgeMin] = useState(25)
  const [ageMax, setAgeMax] = useState(45)
  const [filters, setFilters] = useState<Record<string, string[]>>({})
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [startNumber, setStartNumber] = useState(upload.suggested_start)

  // Le classeur fait foi : un nouveau dépôt réaligne le point de départ.
  useEffect(() => setStartNumber(upload.suggested_start), [upload.suggested_start])

  const code = (value: number) => `PAL-${String(value).padStart(4, '0')}`
  const startsTooLow = startNumber < upload.suggested_start

  const resolvedAgents = autoAgents
    ? Math.max(1, Math.min(profileCount, Math.round(profileCount / 10) || 1))
    : agentCount

  // Un champ numérique vidé vaut 0, et un champ illisible NaN : le serveur les
  // refuse tous deux. On les arrête ici, avec la raison affichée.
  const problems = useMemo(() => {
    const found: string[] = []
    const atLeast = (value: number, min: number, label: string) => {
      if (!Number.isFinite(value) || value < min) found.push(label)
    }
    atLeast(profileCount, 1, 'Le nombre de profils doit valoir au moins 1.')
    atLeast(startNumber, 1, 'Le premier numéro doit valoir au moins 1.')
    atLeast(avatars, 0, "Le nombre d'avatars ne peut pas être négatif.")
    if (!autoAgents) atLeast(agentCount, 1, "Le nombre d'agents doit valoir au moins 1.")
    if (!Number.isFinite(ageMin) || !Number.isFinite(ageMax)) {
      found.push('Les âges doivent être renseignés.')
    } else if (ageMin > ageMax) {
      found.push("L'âge minimum dépasse l'âge maximum.")
    }
    if (countries.length === 0) found.push('Sélectionnez au moins un pays.')
    return found
  }, [profileCount, startNumber, avatars, agentCount, autoAgents, ageMin, ageMax, countries])

  const invalid = problems.length > 0
  // Le bouton de test impose 3 profils : le compteur ne le concerne pas.
  const testBlocked = problems.some((line) => !line.startsWith('Le nombre de profils'))

  const build = (count: number): GenerationRequest => ({
    upload_id: upload.upload_id,
    profile_count: count,
    agent_count: autoAgents ? null : Math.min(agentCount, count),
    avatars_per_profile: avatars,
    countries,
    cities,
    professions,
    age_min: ageMin,
    age_max: ageMax,
    start_number: startNumber,
    field_filters: filters,
  })

  const toggleFilter = (field: string, value: string) => {
    setFilters((current) => {
      const selected = current[field] ?? []
      const next = selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value]
      const updated = { ...current }
      if (next.length === 0) delete updated[field]
      else updated[field] = next
      return updated
    })
  }

  return (
    <>
      <section className="card p-6">
        <h2 className="text-base font-semibold">2 · Configuration</h2>

        <div className="mt-4 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label className="label" htmlFor="count">Nombre de profils</label>
            <input
              id="count"
              type="number"
              min={1}
              max={500}
              className="input"
              value={profileCount}
              onChange={(event) => setProfileCount(Number(event.target.value))}
            />
            <div className="mt-2 flex flex-wrap gap-1.5">
              {PRESETS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => setProfileCount(preset)}
                  className={`chip ${
                    profileCount === preset
                      ? 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-ink-300 bg-white text-ink-700 hover:bg-ink-50'
                  }`}
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="label" htmlFor="agents">Nombre d'agents</label>
            <input
              id="agents"
              type="number"
              min={1}
              max={100}
              className="input"
              value={autoAgents ? resolvedAgents : agentCount}
              disabled={autoAgents}
              onChange={(event) => setAgentCount(Number(event.target.value))}
            />
            <label className="mt-2 flex items-center gap-2 text-sm text-ink-700">
              <input
                type="checkbox"
                checked={autoAgents}
                onChange={(event) => setAutoAgents(event.target.checked)}
              />
              Automatique (≈ 10 profils par agent)
            </label>
          </div>

          <div>
            <label className="label" htmlFor="avatars">Avatars par profil</label>
            <input
              id="avatars"
              type="number"
              min={0}
              max={10}
              className="input"
              value={avatars}
              onChange={(event) => setAvatars(Number(event.target.value))}
            />
            <p className="mt-2 text-xs text-ink-500">
              Illustrations de synthèse, identifiables comme telles.
            </p>
          </div>

          <div>
            <label className="label" htmlFor="ageMin">Âge minimum</label>
            <input
              id="ageMin"
              type="number"
              min={18}
              max={99}
              className="input"
              value={ageMin}
              onChange={(event) => setAgeMin(Number(event.target.value))}
            />
          </div>

          <div>
            <label className="label" htmlFor="ageMax">Âge maximum</label>
            <input
              id="ageMax"
              type="number"
              min={18}
              max={99}
              className="input"
              value={ageMax}
              onChange={(event) => setAgeMax(Number(event.target.value))}
            />
          </div>

          <div>
            <label className="label" htmlFor="start">Premier numéro</label>
            <input
              id="start"
              type="number"
              min={1}
              className="input"
              value={startNumber}
              onChange={(event) => setStartNumber(Number(event.target.value))}
            />
            <p className="mt-2 text-xs text-ink-500">
              {code(startNumber)} → {code(startNumber + profileCount - 1)}
            </p>
            {startsTooLow && (
              <p className="mt-1 text-xs font-medium text-red-700">
                Des codes de ce classeur vont jusqu'à {code(upload.suggested_start - 1)} :
                vous créeriez des doublons.
              </p>
            )}
          </div>
        </div>

        <div className="mt-5 grid gap-5 sm:grid-cols-2">
          <div>
            <span className="label">Pays</span>
            <div className="mb-2 flex flex-wrap gap-1.5">
              {upload.default_countries.map((country) => (
                <button
                  key={country}
                  type="button"
                  onClick={() =>
                    setCountries((current) =>
                      current.includes(country)
                        ? current.filter((item) => item !== country)
                        : [...current, country],
                    )
                  }
                  className={`chip ${
                    countries.includes(country)
                      ? 'border-brand-500 bg-brand-50 text-brand-700'
                      : 'border-ink-300 bg-white text-ink-500 hover:bg-ink-50'
                  }`}
                >
                  {country}
                </button>
              ))}
            </div>
            <TokenList
              values={countries.filter((c) => !upload.default_countries.includes(c))}
              onChange={(custom) =>
                setCountries([
                  ...countries.filter((c) => upload.default_countries.includes(c)),
                  ...custom,
                ])
              }
              placeholder="Ajouter un autre pays…"
            />
          </div>

          <div>
            <span className="label">Villes (facultatif)</span>
            <TokenList values={cities} onChange={setCities} placeholder="Abidjan, Dakar…" />
            <span className="label mt-4">Professions (facultatif)</span>
            <TokenList
              values={professions}
              onChange={setProfessions}
              placeholder="Infirmière, Comptable…"
            />
          </div>
        </div>
      </section>

      <section className="card p-6">
        <button
          type="button"
          className="flex w-full items-center justify-between text-left"
          onClick={() => setShowAdvanced((value) => !value)}
        >
          <span className="text-base font-semibold">3 · Options avancées</span>
          <span className="text-sm text-ink-500">{showAdvanced ? 'Masquer' : 'Afficher'}</span>
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-4">
            <p className="text-sm text-ink-500">
              Restreint les valeurs tirées des listes du classeur. Sans sélection, toute la liste
              du modèle est utilisée.
            </p>
            {ADVANCED_FIELDS.filter((field) => upload.enums[field.key]?.length).map((field) => (
              <div key={field.key}>
                <span className="label">{field.label}</span>
                <div className="flex flex-wrap gap-1.5">
                  {upload.enums[field.key].map((value) => {
                    const active = (filters[field.key] ?? []).includes(value)
                    return (
                      <button
                        key={value}
                        type="button"
                        onClick={() => toggleFilter(field.key, value)}
                        className={`chip ${
                          active
                            ? 'border-brand-500 bg-brand-50 text-brand-700'
                            : 'border-ink-300 bg-white text-ink-500 hover:bg-ink-50'
                        }`}
                      >
                        {value}
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card p-6">
        <h2 className="text-base font-semibold">4 · Résumé</h2>
        <div className="mt-4 flex flex-wrap gap-8">
          <div>
            <p className="text-2xl font-semibold">{profileCount}</p>
            <p className="text-sm text-ink-500">profils</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">{resolvedAgents}</p>
            <p className="text-sm text-ink-500">agents</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">{profileCount * avatars}</p>
            <p className="text-sm text-ink-500">avatars</p>
          </div>
          <div>
            <p className="text-2xl font-semibold">
              {code(startNumber)} <span className="text-ink-300">→</span>{' '}
              {code(startNumber + profileCount - 1)}
            </p>
            <p className="text-sm text-ink-500">codes attribués</p>
          </div>
        </div>

        {profileCount > upload.capacity && (
          <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">
            Le modèle prépare {upload.capacity} lignes. Les lignes supplémentaires seront ajoutées
            avec recopie des formules et des listes déroulantes.
          </p>
        )}
        {problems.length > 0 && (
          <ul className="mt-4 space-y-1 rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">
            {problems.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        )}

        <div className="mt-6 flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-primary"
            disabled={busy || invalid}
            onClick={() => onSubmit(build(profileCount))}
          >
            {busy ? 'Génération en cours…' : 'GÉNÉRER LE DOSSIER'}
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled={busy || testBlocked}
            onClick={() => onSubmit(build(3))}
          >
            Tester avec 3 profils
          </button>
        </div>
      </section>
    </>
  )
}
