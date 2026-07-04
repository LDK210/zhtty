import type { AgentLog, Candidate, Job } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `Request failed with ${response.status}`);
  }
  return response.json();
}

export function listJobs(): Promise<Job[]> {
  return request<Job[]>("/api/jobs");
}

export function createJob(title: string, jdText: string): Promise<Job> {
  return request<Job>("/api/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, jd_text: jdText }),
  });
}

export function getJob(jobId: number): Promise<Job> {
  return request<Job>(`/api/jobs/${jobId}`);
}

export function uploadResumes(jobId: number, files: FileList): Promise<unknown> {
  const form = new FormData();
  Array.from(files).forEach((file) => form.append("files", file));
  return request(`/api/jobs/${jobId}/resumes`, {
    method: "POST",
    body: form,
  });
}

export function runJob(jobId: number): Promise<unknown> {
  return request(`/api/jobs/${jobId}/run`, { method: "POST" });
}

export function getResults(jobId: number): Promise<Candidate[]> {
  return request<Candidate[]>(`/api/jobs/${jobId}/results`);
}

export function getLogs(jobId: number): Promise<AgentLog[]> {
  return request<AgentLog[]>(`/api/jobs/${jobId}/logs`);
}
