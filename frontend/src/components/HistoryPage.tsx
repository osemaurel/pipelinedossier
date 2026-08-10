import { useEffect, useState } from 'react'
import type { HistoryEntry } from '../api'
import { downloadUrl, fetchHistory } from '../api'

const STAGE_LABELS: Record<string, string> = {
  done: 'Terminé',
  error: 'Échec',
  queued: 'En attente',
}

export function HistoryPage() {
  const [entries, setEntries] = useState<HistoryEntry[]>([])
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchHistory()
      .then(setEntries)
      .catch((exc: unknown) =>
        setError(exc instanceof Error ? exc.message : 'Historique indisponible.'),
      )
      .finally(() => setLoading(false))
  }, [])

  return (
    <section className="card overflow-hidden">
      <div className="border-b border-ink-100 px-6 py-5">
        <h2 className="text-base font-semibold">Historique des générations</h2>
        <p className="mt-1 text-sm text-ink-500">
          Les dossiers restent disponibles tant que le serveur conserve ses fichiers de sortie.
        </p>
      </div>

      {loading && <p className="px-6 py-8 text-sm text-ink-500">Chargement…</p>}
      {error && <p className="px-6 py-8 text-sm text-red-700">{error}</p>}
      {!loading && !error && entries.length === 0 && (
        <p className="px-6 py-8 text-sm text-ink-500">Aucune génération pour le moment.</p>
      )}

      {entries.length > 0 && (
        <table className="w-full text-sm">
          <thead className="bg-ink-50 text-left text-xs uppercase tracking-wide text-ink-500">
            <tr>
              <th className="px-6 py-3 font-medium">Date</th>
              <th className="px-6 py-3 font-medium">Job</th>
              <th className="px-6 py-3 font-medium">Profils</th>
              <th className="px-6 py-3 font-medium">Agents</th>
              <th className="px-6 py-3 font-medium">Avatars</th>
              <th className="px-6 py-3 font-medium">Statut</th>
              <th className="px-6 py-3 font-medium">Téléchargements</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-100">
            {entries.map((entry) => (
              <tr key={entry.job_id}>
                <td className="px-6 py-3 whitespace-nowrap">
                  {new Date(entry.created_at).toLocaleString('fr-FR', {
                    dateStyle: 'short',
                    timeStyle: 'short',
                  })}
                </td>
                <td className="px-6 py-3 font-mono text-xs text-ink-500">{entry.job_id}</td>
                <td className="px-6 py-3 tabular-nums">{entry.profiles}</td>
                <td className="px-6 py-3 tabular-nums">{entry.agents}</td>
                <td className="px-6 py-3 tabular-nums">{entry.avatars}</td>
                <td className="px-6 py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      entry.stage === 'done'
                        ? 'bg-emerald-50 text-emerald-700'
                        : entry.stage === 'error'
                          ? 'bg-red-50 text-red-700'
                          : 'bg-ink-100 text-ink-700'
                    }`}
                  >
                    {STAGE_LABELS[entry.stage] ?? 'En cours'}
                  </span>
                </td>
                <td className="px-6 py-3">
                  <div className="flex gap-3">
                    {entry.excel_filename && (
                      <a
                        className="text-brand-600 hover:underline"
                        href={downloadUrl(entry.job_id, 'excel')}
                      >
                        Excel
                      </a>
                    )}
                    {entry.zip_filename && (
                      <a
                        className="text-brand-600 hover:underline"
                        href={downloadUrl(entry.job_id, 'zip')}
                      >
                        ZIP
                      </a>
                    )}
                    {!entry.excel_filename && !entry.zip_filename && (
                      <span className="text-ink-300">—</span>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
