import axios from 'axios'
import type {
  UploadResponse, CompileResponse, ProblemSpace,
  Constraint, SessionSummary,
} from '../types'

const api = axios.create({ baseURL: '/api' })

export async function uploadFiles(formData: FormData): Promise<UploadResponse> {
  const { data } = await api.post<UploadResponse>('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function parseText(request: {
  protocol_text?: string
  csv_analysis?: string
  image_observations?: string
  user_context?: string
  max_runs_budget?: number
}): Promise<UploadResponse> {
  const { data } = await api.post<UploadResponse>('/parse', request)
  return data
}

export async function compile(
  sessionId: string,
  newConstraints: Constraint[] = [],
  updatedBudget?: number,
): Promise<CompileResponse> {
  const { data } = await api.post<CompileResponse>('/compile', {
    session_id: sessionId,
    new_constraints: newConstraints,
    updated_budget: updatedBudget,
  })
  return data
}

export async function addConstraint(
  sessionId: string,
  constraint: Constraint,
): Promise<CompileResponse> {
  const { data } = await api.post<CompileResponse>(`/constrain/${sessionId}`, constraint)
  return data
}

export async function getSession(sessionId: string): Promise<ProblemSpace> {
  const { data } = await api.get<ProblemSpace>(`/session/${sessionId}`)
  return data
}

export async function getCoverage(sessionId: string) {
  const { data } = await api.get(`/coverage/${sessionId}`)
  return data
}

export async function listSessions(): Promise<SessionSummary[]> {
  const { data } = await api.get<SessionSummary[]>('/sessions')
  return data
}

export async function searchCitations(query: string, top = 5) {
  const { data } = await api.get('/search', { params: { q: query, top } })
  return data
}
