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
  existing_profiles: number
  existing_agents: number
  suggested_start: number
  first_free_row: number
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
  start_number: number | null
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

export interface Health {
  status: string
  openai_configured: boolean
  text_model: string
  image_model: string
  // Absents si le moteur qui répond est d'une version antérieure : c'est ce qui
  // permet de détecter un ancien backend resté en place sur le port 8000.
  image_style?: string
  image_size?: string
}

export const EXPECTED_IMAGE_MODEL = 'gpt-image-2'

export type HealthVerdict =
  | { kind: 'ok' }
  | { kind: 'moteur-perime' }
  | { kind: 'config-perimee'; details: string[] }

export function inspectHealth(health: Health): HealthVerdict {
  if (health.image_style === undefined || health.image_size === undefined) {
    return { kind: 'moteur-perime' }
  }
  const details: string[] = []
  if (!health.image_model.includes(EXPECTED_IMAGE_MODEL)) {
    details.push(`modèle d'images « ${health.image_model} » au lieu de « ${EXPECTED_IMAGE_MODEL} »`)
  }
  if (!health.openai_configured) {
    details.push('clé OpenAI absente')
  }
  return details.length ? { kind: 'config-perimee', details } : { kind: 'ok' }
}

/** Message le plus informatif possible : sans détail lisible, on reste aveugle. */
async function describeFailure(response: Response): Promise<string> {
  const raw = await response.text().catch(() => '')
  let detail = ''
  try {
    detail = (JSON.parse(raw) as { detail?: string }).detail ?? ''
  } catch {
    // Réponse non JSON : page d'erreur de l'hébergeur, proxy, ou HTML.
    detail = raw.trim().startsWith('<') ? '' : raw.slice(0, 200)
  }

  if (detail) return detail

  if (response.status === 404) {
    return (
      "Erreur 404 — le serveur n'a pas trouvé cette adresse. C'est typiquement le cas " +
      "pendant un redéploiement : patientez deux minutes, rechargez la page et réessayez."
    )
  }
  if (response.status === 502 || response.status === 503) {
    return 'Le serveur redémarre. Patientez une minute puis rechargez la page.'
  }
  return `Erreur ${response.status} (${response.statusText || 'sans détail'}).`
}

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(await describeFailure(response))
  }
  return response.json() as Promise<T>
}

export async function fetchHealth(): Promise<Health> {
  return unwrap<Health>(await fetch('/api/health'))
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
