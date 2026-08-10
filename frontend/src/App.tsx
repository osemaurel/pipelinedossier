import { useCallback, useEffect, useRef, useState } from 'react'
import type { GenerationRequest, Health, JobStatus, UploadResult } from './api'
import { fetchHealth, resumeJob, startJob, subscribeToJob } from './api'
import { ConfigForm } from './components/ConfigForm'
import { HistoryPage } from './components/HistoryPage'
import { ProgressPanel, ReportPanel } from './components/ProgressPanel'
import { UploadZone } from './components/UploadZone'

type Tab = 'generateur' | 'historique'

const JOB_STORAGE_KEY = 'palab.activeJob'

export default function App() {
  const [tab, setTab] = useState<Tab>('generateur')
  const [upload, setUpload] = useState<UploadResult | null>(null)
  const [status, setStatus] = useState<JobStatus | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [health, setHealth] = useState<Health | null>(null)
  const unsubscribe = useRef<(() => void) | null>(null)

  useEffect(() => {
    fetchHealth().then(setHealth).catch(() => setHealth(null))
  }, [])

  const attach = useCallback((jobId: string) => {
    unsubscribe.current?.()
    unsubscribe.current = subscribeToJob(
      jobId,
      (next) => {
        setStatus(next)
        if (next.stage === 'done' || next.stage === 'error') {
          localStorage.removeItem(JOB_STORAGE_KEY)
        }
      },
      setError,
    )
  }, [])

  // Le job vit côté serveur : un rechargement de page se raccroche au flux.
  useEffect(() => {
    const pending = localStorage.getItem(JOB_STORAGE_KEY)
    if (pending) attach(pending)
    return () => unsubscribe.current?.()
  }, [attach])

  const launch = async (request: GenerationRequest) => {
    setError(null)
    try {
      const created = await startJob(request)
      setStatus(created)
      localStorage.setItem(JOB_STORAGE_KEY, created.job_id)
      attach(created.job_id)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Impossible de lancer la génération.')
    }
  }

  const resume = async () => {
    if (!status) return
    setError(null)
    try {
      const restarted = await resumeJob(status.job_id)
      setStatus(restarted)
      localStorage.setItem(JOB_STORAGE_KEY, restarted.job_id)
      attach(restarted.job_id)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Reprise impossible.')
    }
  }

  const running = Boolean(status && status.stage !== 'done' && status.stage !== 'error')

  return (
    <div className="min-h-screen">
      <header className="border-b border-ink-100 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-end justify-between gap-4 px-6 py-6">
          <div>
            <h1 className="text-xl font-semibold tracking-tight">Palab Dossier Generator</h1>
            <p className="mt-1 text-sm text-ink-500">
              Générez automatiquement vos dossiers de collecte.
            </p>
            {health && (
              <p className="mt-2 font-mono text-xs text-ink-500">
                Images :{' '}
                <span
                  className={
                    health.image_model.includes('image-1')
                      ? 'font-semibold text-amber-700'
                      : 'text-ink-700'
                  }
                >
                  {health.image_model}
                </span>
                {' · '}
                <span
                  className={
                    health.image_style === 'photo'
                      ? 'text-ink-700'
                      : 'font-semibold text-amber-700'
                  }
                >
                  rendu {health.image_style}
                </span>
                {' · '}
                {health.image_size}
              </p>
            )}
          </div>
          <nav className="flex gap-1 rounded-lg bg-ink-100 p-1">
            {([
              ['generateur', 'Générateur'],
              ['historique', 'Historique'],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={`rounded-md px-4 py-1.5 text-sm font-medium transition ${
                  tab === key ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500 hover:text-ink-700'
                }`}
              >
                {label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-6 py-8">
        {tab === 'historique' ? (
          <HistoryPage />
        ) : (
          <>
            <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
              Les dossiers produits contiennent des personnages fictifs de démonstration. Les
              colonnes de vérification (pièce d'identité, contrat de mandat, consentement) ne sont
              pas renseignées automatiquement et le statut reste « À compléter ».
            </div>

            <UploadZone result={upload} onUploaded={setUpload} />

            {upload && <ConfigForm upload={upload} busy={running} onSubmit={launch} />}

            {error && (
              <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
            )}

            {status && <ProgressPanel status={status} onResume={() => void resume()} />}
            {status?.report && <ReportPanel status={status} />}
          </>
        )}
      </main>

      <footer className="mx-auto max-w-5xl px-6 pb-10 text-xs text-ink-500">
        Les appels au modèle passent exclusivement par le backend. La clé API n'est jamais
        transmise au navigateur.
      </footer>
    </div>
  )
}
