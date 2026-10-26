import { CandidateRecord, EducationRecord, Project, WorkExperience } from '../types/candidate';

const EMAIL_RE = /(?:^|\s)([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/i;

const PHONE_RE = /(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)?\d{3,5}[\s.-]?\d{3,5}|0\d{10}|[6-9]\d{9}/g;

const LINKEDIN_RE = /(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[\w\-%.]+\/?/i;

const GITHUB_RE = /(?:https?:\/\/)?(?:www\.)?github\.com\/[\w\-]+\/?/i;

const PORTFOLIO_RE = /https?:\/\/(?:www\.)?(?!linkedin\.com|github\.com|mail\.google|gmail)[\w\-]+\.(?:io|dev|me|site|tech|app|co|com|net|org)\/[\w\-./]*/i;

export function extractEmail(text: string): string | null {
  const match = text.match(EMAIL_RE);
  return match ? match[1].toLowerCase().trim() : null;
}

export function extractPhone(text: string): string | null {
  const matches = text.match(PHONE_RE);
  if (!matches) return null;

  const validCandidates: string[] = [];
  for (const raw of matches) {
    const digits = raw.replace(/\D/g, '');
    if (digits.length >= 8 && digits.length <= 15) {
      validCandidates.push(raw.trim());
    }
  }

  if (validCandidates.length === 0) return null;

  // Prefer match with most digits
  let best = validCandidates[0];
  let maxDigits = best.replace(/\D/g, '').length;
  for (const c of validCandidates) {
    const dCount = c.replace(/\D/g, '').length;
    if (dCount > maxDigits) {
      best = c;
      maxDigits = dCount;
    }
  }

  const cleaned = best.replace(/^(?:phone[-_ ]*(?:alt)?|tel|mobile|cell)\s*[:-]?\s*/i, '').trim();
  return cleaned || best;
}

export function extractLinkedinUrl(text: string): string | null {
  const match = text.match(LINKEDIN_RE);
  if (!match) return null;
  let url = match[0].trim().replace(/\/$/, '');
  if (!/^https?:\/\//i.test(url)) {
    url = 'https://' + url;
  }
  return url;
}

export function extractGithubUrl(text: string): string | null {
  const match = text.match(GITHUB_RE);
  if (!match) return null;
  let url = match[0].trim().replace(/\/$/, '');
  if (!/^https?:\/\//i.test(url)) {
    url = 'https://' + url;
  }
  return url;
}

export function extractPortfolioUrl(text: string): string | null {
  const match = text.match(PORTFOLIO_RE);
  return match ? match[0].trim() : null;
}

export function extractName(text: string): string | null {
  if (!text) return null;
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  for (const line of lines.slice(0, 8)) {
    if (line.includes('@') || line.includes('http') || line.includes('www.') || line.includes('.com') || line.includes('.org') || line.includes('.in')) {
      continue;
    }
    const digits = line.replace(/\D/g, '').length;
    if (digits >= 3) continue;
    if (/^[-*•#>|]/.test(line)) continue;
    const lower = line.toLowerCase();
    if (
      ['curriculum vitae', 'resume', 'cv', 'profile', 'contact', 'experience', 'education', 'skills', 'projects', 'summary', 'objective', 'phone', 'email', 'address'].some((h) => lower.includes(h))
    ) {
      continue;
    }
    let candidate = line.replace(/^(?:name|candidate|user)\s*[:-]\s*/i, '').trim();
    if (candidate.includes(' | ')) candidate = candidate.split(' | ')[0].trim();
    if (candidate.includes(' - ')) candidate = candidate.split(' - ')[0].trim();

    const words = candidate.split(/\s+/);
    if (words.length >= 2 && words.length <= 4) {
      if (words.every((w) => /^[A-Za-z.\-']+$/.test(w))) {
        if (candidate === candidate.toUpperCase()) {
          candidate = candidate.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
        }
        return candidate;
      }
    }
  }
  return null;
}

export function extractLocation(text: string): string | null {
  if (!text) return null;
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean).slice(0, 15);
  const locationRe = /(?:(?:map[-_ ]*marker(?:[-_ ]*alt)?|location|address|residence|city)\s*[:-]?\s*)?([A-Z][a-zA-Z\s]{1,30},\s*[A-Z][a-zA-Z\s]{1,30}(?:\s*,\s*[A-Z][a-zA-Z\s]{1,30})?)/;
  for (const line of lines) {
    const m = line.match(locationRe);
    if (m) {
      const loc = m[1].trim().replace(/^[|,;:-•]+|[|,;:-•]+$/g, '');
      const lower = loc.toLowerCase();
      if (!['university', 'college', 'school', 'technologies', 'institute', 'developer', 'engineer'].some((w) => lower.includes(w))) {
        return loc;
      }
    }
  }
  return null;
}

export function runRuleBasedExtraction(text: string) {
  return {
    email: extractEmail(text),
    phone: extractPhone(text),
    linkedin_url: extractLinkedinUrl(text),
    github_url: extractGithubUrl(text),
    portfolio_url: extractPortfolioUrl(text),
    full_name: extractName(text),
    location: extractLocation(text),
  };
}

export function cleanName(name?: string | null): string | null {
  if (!name || !name.trim()) return null;
  let cleaned = name.trim().replace(/^(?:name\s*[:-]|candidate\s*[:-]|resume\s*[:-]|cv\s*[:-])\s*/i, '').trim();
  if (cleaned.includes(' | ')) {
    cleaned = cleaned.split(' | ')[0].trim();
  } else if (cleaned.includes(' - ')) {
    const parts = cleaned.split(' - ');
    if (parts.length === 2 && ['developer', 'engineer', 'designer', 'intern', 'manager', 'tester', 'student'].some((r) => parts[1].toLowerCase().includes(r))) {
      cleaned = parts[0].trim();
    }
  }
  if (cleaned.length > 2 && cleaned === cleaned.toUpperCase()) {
    cleaned = cleaned.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return cleaned || null;
}

export function cleanPhone(phone?: string | null): string | null {
  if (!phone || !phone.trim()) return null;
  let cleaned = phone.trim().replace(/^(?:phone[-_ ]*(?:alt)?|tel|mobile|cell)\s*[:-]?\s*/i, '').trim();
  return cleaned || null;
}

export function cleanLocation(loc?: string | null): string | null {
  if (!loc || !loc.trim()) return null;
  let cleaned = loc.trim().replace(/^(?:map[-_ ]*marker(?:[-_ ]*alt)?|location|address|city|residence|pin)\s*[:-]?\s*/i, '').trim();
  cleaned = cleaned.replace(/^[|,;:-•]+|[|,;:-•]+$/g, '').trim();
  return cleaned || null;
}

export function cleanUrl(url?: string | null): string | null {
  if (!url || !url.trim()) return null;
  let cleaned = url.trim().replace(/\/$/, '');
  if (!/^https?:\/\//i.test(cleaned)) {
    cleaned = 'https://' + cleaned;
  }
  return cleaned;
}

export function cleanSkillsList(skills: (string | unknown)[]): string[] {
  const cleaned: string[] = [];
  const seen = new Set<string>();
  for (const s of skills) {
    if (!s || typeof s !== 'string') continue;
    const subItems = s.split(',').map((x) => x.trim()).filter(Boolean);
    for (const sub of subItems) {
      const item = sub.replace(/^['"`.,;:-•*[\]()]+|['"`.,;:-•*[\]()]+$/g, '').trim();
      if (item && !seen.has(item.toLowerCase())) {
        seen.add(item.toLowerCase());
        cleaned.push(item);
      }
    }
  }
  return cleaned;
}

export function cleanEducation(edu: EducationRecord): EducationRecord {
  const res = { ...edu };
  if (res.qualification && res.qualification.includes(' in ') && !res.specialization) {
    const parts = res.qualification.split(' in ');
    res.qualification = parts[0].trim();
    res.specialization = parts[1].trim();
  } else if (res.qualification && res.qualification.includes(' - ') && !res.specialization) {
    const parts = res.qualification.split(' - ');
    res.qualification = parts[0].trim();
    res.specialization = parts[1].trim();
  }

  if (res.graduation_year && (res.graduation_year.includes(' - ') || res.graduation_year.includes('–') || res.graduation_year.includes(' to '))) {
    const sep = res.graduation_year.includes(' - ') ? ' - ' : res.graduation_year.includes('–') ? '–' : ' to ';
    const parts = res.graduation_year.split(sep).map((p) => p.trim());
    if (parts.length === 2) {
      const mStart = parts[0].match(/\b(19\d\d|20\d\d)\b/);
      if (mStart && !res.start_year) res.start_year = mStart[1];
      const mEnd = parts[1].match(/\b(19\d\d|20\d\d)\b/);
      res.graduation_year = mEnd ? mEnd[1] : parts[1];
    }
  }
  return res;
}

export function cleanWorkExperience(exp: WorkExperience): WorkExperience {
  const res = { ...exp };
  if (res.start_date && !res.end_date) {
    const s = res.start_date.trim();
    if (s.includes(' - ') || s.includes('–') || s.includes(' to ')) {
      const sep = s.includes(' - ') ? ' - ' : s.includes('–') ? '–' : ' to ';
      const parts = s.split(sep).map((p) => p.trim());
      if (parts.length === 2) {
        res.start_date = parts[0];
        res.end_date = parts[1];
      }
    }
  }

  if (res.responsibilities && Array.isArray(res.responsibilities)) {
    res.responsibilities = res.responsibilities
      .map((r) => String(r).replace(/^[\s•*–\-\u2022\u25cf\u25cb\u25aa\d.]+\s*/, '').trim())
      .filter(Boolean);
  } else {
    res.responsibilities = [];
  }

  if (res.responsibilities.length === 0 && res.description) {
    const lines = res.description.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length > 1 || (lines[0] && /^[\s•*–\-\u2022\u25cf]/.test(lines[0]))) {
      res.responsibilities = lines.map((l) => l.replace(/^[\s•*–\-\u2022\u25cf\u25cb\u25aa\d.]+\s*/, '').trim()).filter(Boolean);
      res.description = null;
    }
  }
  return res;
}

export function cleanProject(proj: Project): Project {
  const res = { ...proj, technologies: [...(proj.technologies || [])] };
  if (res.name) {
    let name = res.name.trim();
    if (name.includes('|')) {
      const parts = name.split('|');
      res.name = parts[0].trim();
      if (parts.length > 1 && res.technologies.length === 0) {
        res.technologies = parts[1].split(',').map((t) => t.trim()).filter(Boolean);
      }
    } else if (name.includes('(') && name.endsWith(')')) {
      const m = name.match(/^(.*?)\s*\((.*?)\)$/);
      if (m) {
        res.name = m[1].trim();
        if (res.technologies.length === 0) {
          res.technologies = m[2].split(',').map((t) => t.trim()).filter(Boolean);
        }
      }
    }
  }
  return res;
}

export function mergeResults(ruleData: Record<string, any>, aiData: Record<string, any>): Record<string, any> {
  const merged: Record<string, any> = { ...aiData };
  const priorityFields = ['email', 'phone', 'linkedin_url', 'github_url', 'portfolio_url'];
  const conflicts: string[] = [];

  for (const field of priorityFields) {
    const ruleVal = ruleData[field];
    const aiVal = aiData[field];

    if (ruleVal !== null && ruleVal !== undefined && ruleVal !== '') {
      if (field === 'phone' && aiVal) {
        const ruleDigits = String(ruleVal).replace(/\D/g, '');
        const aiDigits = String(aiVal).replace(/\D/g, '');
        if (String(aiVal).trim().startsWith('+') && aiDigits.endsWith(ruleDigits)) {
          merged[field] = aiVal;
          continue;
        }
      }
      if (aiVal && aiVal !== ruleVal) {
        conflicts.push(`${field}: rule='${ruleVal}' vs ai='${aiVal}' — kept rule value`);
      }
      merged[field] = ruleVal;
    } else if (aiVal) {
      merged[field] = aiVal;
    }
  }

  merged._conflicts = conflicts;
  return merged;
}
