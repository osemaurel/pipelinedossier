import { useCallback, useRef, useState } from 'react'
import type { UploadResult } from '../api'
import { uploadModel } from '../api'

interface Props {
  result: UploadResult | null
  onUploaded: (result: UploadResult) => void
}

export function UploadZone({ result, onUploaded }: Props) {
  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return
      setBusy(true)
      setError(null)
      try {
        onUploaded(await uploadModel(file))
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : 'Téléversement impossible.')
      } finally {
        setBusy(false)
      }
    },
    [onUploaded],
  )

  return (
    <section className="card p-6">
      <h2 className="text-base font-semibold">1 · Importer le modèle Excel</h2>
      <p className="mt-1 text-sm text-ink-500">
        Le classeur déposé sert de référence : ses feuilles, colonnes, formules et listes
        déroulantes sont analysées puis conservées. Le fichier d'origine n'est jamais modifié.
      </p>

      <div
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          void handleFile(event.dataTransfer.files[0])
        }}
        onClick={() => inputRef.current?.click()}
        className={`mt-4 cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition ${
          dragging ? 'border-brand-500 bg-brand-50' : 'border-ink-300 bg-ink-50 hover:bg-ink-100'
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx,.xlsm"
          className="hidden"
          onChange={(event) => void handleFile(event.target.files?.[0])}
        />
        <p className="text-sm font-medium">
          {busy ? 'Analyse du classeur…' : 'Déposez votre fichier Excel ici'}
        </p>
        <p className="mt-1 text-xs text-ink-500">ou cliquez pour parcourir · .xlsx ou .xlsm</p>
      </div>

      {error && (
        <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>
      )}

      {result && (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm font-medium text-emerald-900">
            {result.filename} — modèle analysé
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-1.5 text-xs text-emerald-900 sm:grid-cols-4">
            <div>
              <dt className="text-emerald-700">Feuilles</dt>
              <dd className="font-medium">{result.sheets.join(', ')}</dd>
            </div>
            <div>
              <dt className="text-emerald-700">Colonnes Femmes</dt>
              <dd className="font-medium">{result.femmes_columns}</dd>
            </div>
            <div>
              <dt className="text-emerald-700">Colonnes Agents</dt>
              <dd className="font-medium">{result.agents_columns}</dd>
            </div>
            <div>
              <dt className="text-emerald-700">Lignes préparées</dt>
              <dd className="font-medium">{result.capacity}</dd>
            </div>
          </dl>

          {result.existing_profiles > 0 && (
            <p className="mt-3 rounded-md border border-emerald-300 bg-white px-3 py-2 text-xs leading-relaxed text-emerald-900">
              <span className="font-medium">
                {result.existing_profiles} profil{result.existing_profiles > 1 ? 's' : ''} déjà
                présent{result.existing_profiles > 1 ? 's' : ''} dans ce classeur.
              </span>{' '}
              Les nouveaux seront ajoutés à partir de la ligne {result.first_free_row}, sans
              rien écraser, et la numérotation reprendra à{' '}
              <span className="font-mono font-medium">
                PAL-{String(result.suggested_start).padStart(4, '0')}
              </span>
              .
            </p>
          )}

          {result.withheld.length > 0 && (
            <p className="mt-3 border-t border-emerald-200 pt-3 text-xs leading-relaxed text-emerald-800">
              <span className="font-medium">Colonnes non renseignées automatiquement :</span>{' '}
              {result.withheld.join(' · ')}. Elles attestent qu'un document a été vérifié par une
              personne ; elles reçoivent « N/A — démonstration » et le dossier reste « À compléter ».
            </p>
          )}
        </div>
      )}
    </section>
  )
}
