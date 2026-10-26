import ExcelJS from 'exceljs';
import { CandidateRecord, EducationRecord, FailedDocument } from '../types/candidate';
import { sanitiseFormulaInjection } from './validator';

const HEADER_FILL: ExcelJS.Fill = {
  type: 'pattern',
  pattern: 'solid',
  fgColor: { argb: 'FF1F497D' }, // dark blue
};

const HEADER_FONT: Partial<ExcelJS.Font> = {
  name: 'Calibri',
  size: 11,
  bold: true,
  color: { argb: 'FFFFFFFF' },
};

const STATUS_FILLS: Record<string, ExcelJS.Fill> = {
  success: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFC6EFCE' } }, // light green
  partial: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFEB9C' } }, // light amber
  review_required: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFEB9C' } }, // light amber
  failed: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFC7CE' } }, // light red
  pending: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFDDDDDD' } }, // grey
};

function safe(val?: string | number | null): string {
  if (val === null || val === undefined) return '';
  return sanitiseFormulaInjection(String(val));
}

function safeJoin(items?: string[], sep = '; '): string {
  if (!items || !Array.isArray(items)) return '';
  return items.filter(Boolean).join(sep);
}

function getHighestEducation(records: EducationRecord[]): EducationRecord | null {
  if (!records || records.length === 0) return null;

  function rank(edu: EducationRecord): [number, number] {
    const q = (edu.qualification || '').toLowerCase();
    let level = 0;
    if (['ph.d', 'phd', 'doctorate', 'doctoral'].some((w) => q.includes(w))) level = 5;
    else if (['m.tech', 'm.e.', 'm.s.', 'm.sc', 'mca', 'mba', 'master'].some((w) => q.includes(w))) level = 4;
    else if (['b.tech', 'b.e.', 'b.s.', 'b.sc', 'bca', 'bba', 'bachelor', 'degree'].some((w) => q.includes(w))) level = 3;
    else if (['diploma', 'polytechnic'].some((w) => q.includes(w))) level = 2;
    else if (['hsc', 'ssc', '12th', '10th', 'high school', 'secondary'].some((w) => q.includes(w))) level = 1;

    let yr = 0;
    if (edu.graduation_year) {
      const m = String(edu.graduation_year).match(/\b(19\d\d|20\d\d)\b/);
      if (m) yr = parseInt(m[1], 10);
    }
    return [level, yr];
  }

  let highest = records[0];
  let highestRank = rank(highest);
  for (let i = 1; i < records.length; i++) {
    const currentRank = rank(records[i]);
    if (currentRank[0] > highestRank[0] || (currentRank[0] === highestRank[0] && currentRank[1] > highestRank[1])) {
      highest = records[i];
      highestRank = currentRank;
    }
  }
  return highest;
}

function styleHeaderRow(ws: ExcelJS.Worksheet, colCount: number) {
  const row = ws.getRow(1);
  row.height = 24;
  for (let c = 1; c <= colCount; c++) {
    const cell = row.getCell(c);
    cell.fill = HEADER_FILL;
    cell.font = HEADER_FONT;
    cell.alignment = { vertical: 'middle', horizontal: 'left', wrapText: true };
  }
}

export async function generateExcelWorkbook(
  records: CandidateRecord[],
  failedDocs: FailedDocument[] = []
): Promise<Blob> {
  const wb = new ExcelJS.Workbook();
  wb.creator = 'ResumeDrop';
  wb.lastModifiedBy = 'ResumeDrop';
  wb.created = new Date();
  wb.modified = new Date();

  // -------------------------------------------------------------
  // Sheet 1: Candidates
  // -------------------------------------------------------------
  const wsCandidates = wb.addWorksheet('Candidates', {
    views: [{ state: 'frozen', xSplit: 0, ySplit: 1 }],
  });

  const candHeaders = [
    'Candidate ID', 'Resume Filename', 'Full Name', 'Email', 'Phone',
    'Location', 'Highest Qualification', 'Specialization', 'Institution',
    'Graduation Year', 'All Education',
    'Technical Skills', 'Programming Languages', 'Tools',
    'Total Experience (jobs)', 'Certifications',
    'LinkedIn URL', 'GitHub URL', 'Portfolio URL',
    'Processing Status', 'Extraction Method',
    'Missing Fields', 'Validation Issues', 'Review Notes',
  ];

  wsCandidates.addRow(candHeaders);
  styleHeaderRow(wsCandidates, candHeaders.length);

  const candColWidths = [
    14, 24, 22, 28, 16, 20,
    22, 20, 26, 14, 40,
    30, 26, 26,
    10, 30,
    30, 30, 30,
    18, 14,
    24, 40, 32,
  ];
  candColWidths.forEach((w, i) => {
    wsCandidates.getColumn(i + 1).width = w;
  });

  for (const rec of records) {
    const highestEdu = getHighestEducation(rec.education);
    const allEdu = rec.education
      .map((e) => [e.qualification, e.specialization, e.institution, e.graduation_year].filter(Boolean).join(' | '))
      .join('; ');

    const status = rec.metadata.processing_status;

    const row = wsCandidates.addRow([
      safe(rec.candidate_id),
      safe(rec.resume_filename),
      safe(rec.full_name),
      safe(rec.email),
      safe(rec.phone), // plain text
      safe(rec.location),
      safe(highestEdu?.qualification),
      safe(highestEdu?.specialization),
      safe(highestEdu?.institution),
      safe(highestEdu?.graduation_year),
      safe(allEdu),
      safeJoin(rec.technical_skills),
      safeJoin(rec.programming_languages),
      safeJoin(rec.tools),
      String(rec.work_experience.length),
      safeJoin(rec.certifications),
      safe(rec.linkedin_url),
      safe(rec.github_url),
      safe(rec.portfolio_url),
      safe(status),
      safe(rec.metadata.extraction_method),
      safeJoin(rec.metadata.missing_fields, ', '),
      safeJoin(rec.metadata.validation_issues),
      safeJoin(rec.metadata.review_notes),
    ]);

    row.alignment = { vertical: 'top' };

    // Colour status cell (col 20)
    const statusCell = row.getCell(20);
    const fill = STATUS_FILLS[status] || STATUS_FILLS.pending;
    statusCell.fill = fill;

    // Wrap long columns
    [11, 12, 13, 14, 16, 22, 23, 24].forEach((c) => {
      row.getCell(c).alignment = { wrapText: true, vertical: 'top' };
    });
  }

  wsCandidates.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: candHeaders.length },
  };

  // -------------------------------------------------------------
  // Sheet 2: Education
  // -------------------------------------------------------------
  const wsEdu = wb.addWorksheet('Education', {
    views: [{ state: 'frozen', xSplit: 0, ySplit: 1 }],
  });
  const eduHeaders = [
    'Candidate ID', 'Resume Filename', 'Full Name',
    'Qualification', 'Specialization', 'Institution',
    'Start Year', 'Graduation Year',
  ];
  wsEdu.addRow(eduHeaders);
  styleHeaderRow(wsEdu, eduHeaders.length);
  [14, 24, 22, 26, 22, 30, 12, 14].forEach((w, i) => {
    wsEdu.getColumn(i + 1).width = w;
  });

  for (const rec of records) {
    for (const edu of rec.education) {
      const row = wsEdu.addRow([
        safe(rec.candidate_id),
        safe(rec.resume_filename),
        safe(rec.full_name),
        safe(edu.qualification),
        safe(edu.specialization),
        safe(edu.institution),
        safe(edu.start_year),
        safe(edu.graduation_year),
      ]);
      row.alignment = { vertical: 'top' };
    }
  }

  wsEdu.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: eduHeaders.length },
  };

  // -------------------------------------------------------------
  // Sheet 3: Work Experience
  // -------------------------------------------------------------
  const wsExp = wb.addWorksheet('Work Experience', {
    views: [{ state: 'frozen', xSplit: 0, ySplit: 1 }],
  });
  const expHeaders = [
    'Candidate ID', 'Resume Filename', 'Full Name',
    'Employer', 'Job Title', 'Start Date', 'End Date',
    'Responsibilities', 'Description',
  ];
  wsExp.addRow(expHeaders);
  styleHeaderRow(wsExp, expHeaders.length);
  [14, 24, 22, 26, 22, 14, 14, 50, 40].forEach((w, i) => {
    wsExp.getColumn(i + 1).width = w;
  });

  for (const rec of records) {
    for (const exp of rec.work_experience) {
      let respStr = '';
      if (exp.responsibilities && exp.responsibilities.length > 0) {
        respStr = '• ' + exp.responsibilities.join('\n• ');
      }
      const row = wsExp.addRow([
        safe(rec.candidate_id),
        safe(rec.resume_filename),
        safe(rec.full_name),
        safe(exp.employer),
        safe(exp.job_title),
        safe(exp.start_date),
        safe(exp.end_date),
        safe(respStr),
        safe(exp.description),
      ]);
      row.alignment = { vertical: 'top' };
      row.getCell(8).alignment = { wrapText: true, vertical: 'top' };
      row.getCell(9).alignment = { wrapText: true, vertical: 'top' };
    }
  }

  wsExp.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: expHeaders.length },
  };

  // -------------------------------------------------------------
  // Sheet 4: Projects
  // -------------------------------------------------------------
  const wsProj = wb.addWorksheet('Projects', {
    views: [{ state: 'frozen', xSplit: 0, ySplit: 1 }],
  });
  const projHeaders = [
    'Candidate ID', 'Resume Filename', 'Full Name',
    'Project Name', 'Description', 'Technologies',
  ];
  wsProj.addRow(projHeaders);
  styleHeaderRow(wsProj, projHeaders.length);
  [14, 24, 22, 28, 50, 30].forEach((w, i) => {
    wsProj.getColumn(i + 1).width = w;
  });

  for (const rec of records) {
    for (const proj of rec.projects) {
      const row = wsProj.addRow([
        safe(rec.candidate_id),
        safe(rec.resume_filename),
        safe(rec.full_name),
        safe(proj.name),
        safe(proj.description),
        safeJoin(proj.technologies),
      ]);
      row.alignment = { vertical: 'top' };
      row.getCell(5).alignment = { wrapText: true, vertical: 'top' };
    }
  }

  wsProj.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: projHeaders.length },
  };

  // -------------------------------------------------------------
  // Sheet 5: Processing Log
  // -------------------------------------------------------------
  const wsLog = wb.addWorksheet('Processing Log', {
    views: [{ state: 'frozen', xSplit: 0, ySplit: 1 }],
  });
  const logHeaders = [
    'Resume Filename', 'Document Status', 'Extraction Status',
    'Extraction Method', 'Characters Extracted',
    'Missing Fields', 'Validation Issues', 'Failure Reason',
    'Extracted At',
  ];
  wsLog.addRow(logHeaders);
  styleHeaderRow(wsLog, logHeaders.length);
  [28, 18, 18, 16, 18, 24, 40, 40, 26].forEach((w, i) => {
    wsLog.getColumn(i + 1).width = w;
  });

  for (const rec of records) {
    const status = rec.metadata.processing_status;
    const row = wsLog.addRow([
      safe(rec.resume_filename),
      'success',
      safe(status),
      safe(rec.metadata.extraction_method),
      rec.raw_text_snippet ? rec.raw_text_snippet.length * 10 : 0,
      safeJoin(rec.metadata.missing_fields, ', '),
      safeJoin(rec.metadata.validation_issues),
      '',
      safe(rec.metadata.extracted_at),
    ]);
    row.alignment = { vertical: 'top' };
    row.getCell(3).fill = STATUS_FILLS[status] || STATUS_FILLS.pending;
    [6, 7, 8].forEach((c) => {
      row.getCell(c).alignment = { wrapText: true, vertical: 'top' };
    });
  }

  for (const failed of failedDocs) {
    const row = wsLog.addRow([
      safe(failed.filename),
      safe(failed.doc_status || 'failed'),
      'failed',
      'none',
      failed.char_count || 0,
      '',
      '',
      safe(failed.error || ''),
      '',
    ]);
    row.alignment = { vertical: 'top' };
    row.getCell(3).fill = STATUS_FILLS.failed;
    [6, 7, 8].forEach((c) => {
      row.getCell(c).alignment = { wrapText: true, vertical: 'top' };
    });
  }

  wsLog.autoFilter = {
    from: { row: 1, column: 1 },
    to: { row: 1, column: logHeaders.length },
  };

  const buffer = await wb.xlsx.writeBuffer();
  return new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
}
