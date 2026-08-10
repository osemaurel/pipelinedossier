import type { JobStage, JobStatus } from '../api'
import { downloadUrl } from '../api'

const STAGES: { key: JobStage; label: string }[] = [
  { key: 'analyse', label: 'Analyse du fichier Excel' },
  { key: 'agents', label: 'Génération des agents' },
  { key: 'profils', label: 'Génération des profils' },
  { key: 'validation', label: 'Validation des profils' },
  { key: 'avatars', label: 'Génération des avatars' },
  { key: 'excel', label: 'Remplissage Excel' },
  { key: 'zip', label: 'Création du ZIP' },
]

function progressOf(status: JobStatus): number {
  const base: Record<string, number> = {
    queued: 0, analyse: 3, agents: 8, profils: 10, validation: 55,
    avatars: 60, excel: 92, zip: 96, done: 100, error: 100,
  }
  const value = base[status.stage] ?? 0
  if (status.stage === 'profils' && status.profiles_total) {
    return value + 45 * (status.profiles_done / status.profiles_total)
  }
  if (status.stage === 'avatars' && status.avatars_total) {
    return value + 32 * (status.avatars_done / status.avatars_total)
  }
  return value
}

export function ProgressPanel({
  status,
  onResume,
}: {
  status: JobStatus
  onResume?: () => void
}) {
  const done = status.stage === 'done'
  const failed = status.stage === 'error'
  const percent = Math.round(progressOf(status))

  const marker = (stage: JobStage) => {
    if (status.completed_stages.includes(stage) || done) return '✓'
    if (status.stage === stage) return failed ? '✗' : '⏳'
    return '○'
  }

  return (
    <section className="card p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">
            {done ? 'Dossier terminé ✓' : failed ? 'Génération interrompue' : 'Génération du dossier…'}
          </h2>
          <p className="mt-1 font-mono text-xs text-ink-500">{status.job_id}</p>
        </div>
        <span className="text-2xl font-semibold tabular-nums">{percent}%</span>
      </div>

      <div className="mt-4 h-2 overflow-hidden rounded-full bg-ink-100">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            failed ? 'bg-red-500' : done ? 'bg-emerald-500' : 'bg-brand-600'
          }`}
          style={{ width: `${percent}%` }}
        />
      </div>

      <ul className="mt-5 space-y-1.5 font-mono text-sm">
        {STAGES.map((stage) => {
          const active = status.stage === stage.key
          const complete = status.completed_stages.includes(stage.key) || done
          return (
            <li
              key={stage.key}
              className={
                complete ? 'text-emerald-700' : active ? 'text-ink-900' : 'text-ink-300'
              }
            >
              {marker(stage.key)} {stage.label}
              {active && stage.key === 'profils' && status.profiles_total > 0 && (
                <span className="ml-2 text-ink-500">
                  {status.profiles_done} / {status.profiles_total} profils
                </span>
              )}
              {active && stage.key === 'avatars' && status.avatars_total > 0 && (
                <span className="ml-2 text-ink-500">
                  {status.avatars_done} / {status.avatars_total} avatars
                </span>
              )}
            </li>
          )
        })}
      </ul>

      {failed && (
        <div className="mt-4 rounded-lg bg-red-50 px-3 py-3 text-sm text-red-700">
          {status.error && <p>{status.error}</p>}
          {onResume && (
            <button type="button" className="btn-secondary mt-3" onClick={onResume}>
              Reprendre depuis le dernier point de contrôle
            </button>
          )}
        </div>
      )}

      {done && (
        <div className="mt-6 flex flex-wrap gap-3 border-t border-ink-100 pt-5">
          <a className="btn-primary" href={downloadUrl(status.job_id, 'zip')}>
            Télécharger le ZIP complet
          </a>
          <a className="btn-secondary" href={downloadUrl(status.job_id, 'excel')}>
            Télécharger Excel
          </a>
        </div>
      )}
    </section>
  )
}

export function ReportPanel({ status }: { status: JobStatus }) {
  if (!status.report) return null
  const { report } = status
  const errors = report.issues.filter((issue) => issue.severity === 'erreur')
  const warnings = report.issues.filter((issue) => issue.severity !== 'erreur')

  return (
    <section className="card p-6">
      <h2 className="text-base font-semibold">Rapport de validation</h2>
      <pre className="mt-4 overflow-x-auto rounded-lg bg-ink-50 p-4 text-xs leading-relaxed text-ink-700">
        {report.checks.join('\n')}
      </pre>

      {errors.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-red-700">Erreurs</h3>
          <ul className="mt-2 space-y-1 text-sm text-red-700">
            {errors.map((issue, index) => (
              <li key={index}>✗ [{issue.scope}] {issue.message}</li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold text-amber-700">Avertissements</h3>
          <ul className="mt-2 space-y-1 text-sm text-amber-700">
            {warnings.map((issue, index) => (
              <li key={index}>! [{issue.scope}] {issue.message}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
