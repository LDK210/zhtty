export type JobStatus = "draft" | "ready" | "running" | "completed" | "failed";
export type ResumeStatus = "uploaded" | "extracting" | "parsed" | "scored" | "completed" | "failed";

export interface Resume {
  id: number;
  original_filename: string;
  status: ResumeStatus;
  error_message: string | null;
  created_at: string;
}

export interface Job {
  id: number;
  title: string;
  jd_text: string;
  status: JobStatus;
  error_message: string | null;
  created_at: string;
  resumes: Resume[];
  progress: Record<ResumeStatus, number>;
}

export interface Score {
  total_score: number;
  level: string;
  score_detail_json: Record<string, number>;
  matched_points_json: string[];
  missing_points_json: string[];
  interview_questions_json: string[];
  invitation_message: string;
  summary: string;
}

export interface Candidate {
  id: number;
  resume_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  structured_json: {
    skills?: string[];
    summary?: string;
    projects?: Array<{ name?: string; description?: string; tech_stack?: string[] }>;
    education?: Array<Record<string, string>>;
  };
  score: Score;
}

export interface AgentLog {
  id: number;
  resume_id: number | null;
  step: string;
  message: string;
  status: string;
  created_at: string;
}
