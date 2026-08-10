export type JobStage =
  | 'queued' | 'analyse' | 'agents' | 'profils' | 'validation'
  | 'avatars' | 'excel' | 'zip' | 'done' | 'error'

export interface UploadResult {
  upload_id: string
  filename: string
  sheets: string[]
  femmes_columns: number
  agents_columns: number
  photos_columns: number
  capacity: number
  text_rules: Record<string, (number | null)[]>
  enums: Record<string, string[]>
  withheld: string[]
  default_countries: string[]
}

export interface GenerationRequest {
  upload_id: string
  profile_count: number
  agent_count: number | null
  avatars_per_profile: number
  countries: string[]
  cities: string[]
  professions: string[]
  age_min: number
  age_max: number
  field_filters: Record<string, string[]>
}

export interface ValidationIssue {
  severity: string
  scope: string
  message: string
}

export interface ValidationReport {
  checks: string[]
  issues: ValidationIssue[]
  profiles: number
  agents: number
  avatars: number
}

export interface JobStatus {
  job_id: string
  stage: JobStage
  stage_label: string
  created_at: string
  updated_at: string
  profiles_done: number
  profiles_total: number
  avatars_done: number
  avatars_total: number
  completed_stages: string[]
  messages: string[]
  error: string | null
  excel_filename: string | null
  zip_filename: string | null
  report: ValidationReport | null
}

export interface HistoryEntry {
  job_id: string
  created_at: string
  stage: JobStage
  profiles: number
  agents: number
  avatars: number
  excel_filename: string | null
  zip_filename: string | null
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `Erreur ${response.status}`)
  }
  return response.json() as Promise<T>
}

export async function uploadModel(file: File): Promise<UploadResult> {
  const body = new FormData()
  body.append('file', file)
  return unwrap<UploadResult>(await fetch('/api/upload', { method: 'POST', body }))
}

export async function startJob(request: GenerationRequest): Promise<JobStatus> {
  return unwrap<JobStatus>(
    await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    }),
  )
}

/** Relance un job interrompu sans régénérer ce qui est déjà produit. */
export async function resumeJob(jobId: string): Promise<JobStatus> {
  return unwrap<JobStatus>(await fetch(`/api/jobs/${jobId}/resume`, { method: 'POST' }))
}

export async function fetchHistory(): Promise<HistoryEntry[]> {
  return unwrap<HistoryEntry[]>(await fetch('/api/history'))
}

/** Flux de progression (SSE). Renvoie la fonction de fermeture. */
export function subscribeToJob(
  jobId: string,
  onUpdate: (status: JobStatus) => void,
  onError: (message: string) => void,
): () => void {
  const source = new EventSource(`/api/jobs/${jobId}/events`)

  source.onmessage = (event) => {
    try {
      const status = JSON.parse(event.data) as JobStatus
      onUpdate(status)
      if (status.stage === 'done' || status.stage === 'error') source.close()
    } catch {
      onError('Réponse de progression illisible.')
    }
  }
  source.onerror = () => {
    // Le flux se ferme normalement à la fin du job ; on ne signale que les
    // coupures survenant alors que la connexion était encore ouverte.
    if (source.readyState !== EventSource.CLOSED) {
      onError('Connexion au suivi interrompue.')
    }
    source.close()
  }

  return () => source.close()
}

export const downloadUrl = (jobId: string, kind: 'excel' | 'zip') =>
  `/api/jobs/${jobId}/download/${kind}`
