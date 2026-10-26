export interface EducationRecord {
  qualification?: string | null;
  specialization?: string | null;
  institution?: string | null;
  start_year?: string | null;
  graduation_year?: string | null;
}

export interface WorkExperience {
  employer?: string | null;
  job_title?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  summary?: string | null;
  responsibilities: string[];
  description?: string | null;
}

export interface Project {
  name?: string | null;
  summary?: string | null;
  description?: string | null;
  technologies: string[];
}

export interface ExtractionMetadata {
  processing_status: 'pending' | 'success' | 'partial' | 'review_required' | 'failed';
  missing_fields: string[];
  validation_issues: string[];
  review_notes: string[];
  extraction_method: 'rules_only' | 'ai' | 'rules+ai' | 'none';
  model_used?: string | null;
  extracted_at?: string | null;
}

export interface CandidateRecord {
  candidate_id: string;
  resume_filename: string;
  full_name?: string | null;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  education: EducationRecord[];
  technical_skills: string[];
  programming_languages: string[];
  tools: string[];
  work_experience: WorkExperience[];
  projects: Project[];
  certifications: string[];
  linkedin_url?: string | null;
  github_url?: string | null;
  portfolio_url?: string | null;
  metadata: ExtractionMetadata;
  raw_text_snippet?: string | null;
}

export type ProcessingStatus =
  | 'success'
  | 'empty'
  | 'unsupported_format'
  | 'file_too_large'
  | 'empty_file'
  | 'duplicate'
  | 'corrupt'
  | 'password_protected'
  | 'error';

export interface DocumentResult {
  filename: string;
  status: ProcessingStatus;
  text: string;
  error?: string;
  file_hash?: string;
  char_count: number;
}

export interface FailedDocument {
  filename: string;
  doc_status: string;
  error?: string;
  char_count?: number;
}

export interface SyntheticDatasetItem {
  id: string;
  notes: string;
  text: string;
  expected: {
    full_name?: string | null;
    email?: string | null;
    phone?: string | null;
    location?: string | null;
    education_count?: number;
    graduation_years?: string[];
    has_technical_skills?: boolean;
    work_experience_count?: number;
    project_count?: number;
    certification_count?: number;
    linkedin_url_present?: boolean;
    github_url_present?: boolean;
    portfolio_url_present?: boolean;
  };
}
