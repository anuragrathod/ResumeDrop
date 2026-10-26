import { CandidateRecord, EducationRecord } from '../types/candidate';

const MIN_GRAD_YEAR = 1950;
const MAX_GRAD_YEAR = 2035;
const FORMULA_PREFIXES = ['=', '+', '-', '@', '\t', '\r'];
const VALID_EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

export function validateEmail(email?: string | null): string | null {
  if (!email) return null;
  const trimmed = email.trim();
  if (!VALID_EMAIL_RE.test(trimmed)) {
    return `Email '${trimmed}' does not appear to be valid.`;
  }
  return null;
}

export function validatePhone(phone?: string | null): string | null {
  if (!phone) return null;
  const digits = phone.replace(/\D/g, '');
  if (digits.length < 7) {
    return `Phone '${phone}' has fewer than 7 digits — likely not a phone number.`;
  }
  if (digits.length > 15) {
    return `Phone '${phone}' has more than 15 digits — likely not a phone number.`;
  }
  return null;
}

export function validateGraduationYears(record: CandidateRecord): string[] {
  const issues: string[] = [];
  for (const edu of record.education) {
    for (const attr of ['graduation_year', 'start_year'] as const) {
      const raw = edu[attr];
      if (!raw) continue;
      const match = raw.match(/\b(19|20)\d{2}\b/);
      if (match) {
        const year = parseInt(match[0], 10);
        if (year < MIN_GRAD_YEAR || year > MAX_GRAD_YEAR) {
          issues.push(
            `Education ${attr} '${raw}' is outside the plausible range (${MIN_GRAD_YEAR}–${MAX_GRAD_YEAR}).`
          );
        }
      }
    }
  }
  return issues;
}

export function sanitiseFormulaInjection(value?: string | null): string {
  if (!value) return '';
  const str = String(value);
  if (FORMULA_PREFIXES.some((prefix) => str.startsWith(prefix))) {
    return "'" + str;
  }
  return str;
}

export function findDuplicates<T>(items: T[], keyFn: (item: T) => string): string[] {
  const seen = new Set<string>();
  const dupes: string[] = [];
  for (const item of items) {
    const k = keyFn(item).trim().toLowerCase();
    if (k && seen.has(k)) {
      dupes.push(keyFn(item));
    } else if (k) {
      seen.add(k);
    }
  }
  return dupes;
}

export function validateCandidate(record: CandidateRecord): CandidateRecord {
  // Clear previous validation issues to allow re-validation on edit
  record.metadata.validation_issues = [];
  record.metadata.review_notes = [];

  // Email validation
  const emailIssue = validateEmail(record.email);
  if (emailIssue) {
    record.metadata.validation_issues.push(emailIssue);
  }

  // Phone validation
  const phoneIssue = validatePhone(record.phone);
  if (phoneIssue) {
    record.metadata.validation_issues.push(phoneIssue);
  }

  // Graduation year validation
  const gradIssues = validateGraduationYears(record);
  for (const issue of gradIssues) {
    record.metadata.validation_issues.push(issue);
  }

  // Duplicate education records
  const eduDupes = findDuplicates(
    record.education,
    (e) => `${e.institution || ''}_${e.qualification || ''}`
  );
  for (const dupe of eduDupes) {
    record.metadata.review_notes.push(`Duplicate education entry detected: '${dupe}'`);
  }

  // Duplicate work experience records
  const expDupes = findDuplicates(
    record.work_experience,
    (e) => `${e.employer || ''}_${e.job_title || ''}`
  );
  for (const dupe of expDupes) {
    record.metadata.review_notes.push(`Duplicate work experience entry detected: '${dupe}'`);
  }

  // Check missing fields
  record.metadata.missing_fields = [];
  if (!record.full_name) record.metadata.missing_fields.push('full_name');
  if (!record.email) record.metadata.missing_fields.push('email');
  if (!record.phone) record.metadata.missing_fields.push('phone');
  if (!record.education || record.education.length === 0) record.metadata.missing_fields.push('education');
  if (
    (!record.technical_skills || record.technical_skills.length === 0) &&
    (!record.programming_languages || record.programming_languages.length === 0) &&
    (!record.tools || record.tools.length === 0)
  ) {
    record.metadata.missing_fields.push('technical_skills');
  }

  // Final processing status
  if (record.metadata.validation_issues.length > 0 && record.metadata.processing_status === 'success') {
    record.metadata.processing_status = 'review_required';
  }

  return record;
}
