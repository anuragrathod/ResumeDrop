import { DocumentResult, ProcessingStatus } from '../types/candidate';
import mammoth from 'mammoth';

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const MIN_TEXT_CHARS = 50;

export async function computeSha256(buffer: ArrayBuffer): Promise<string> {
  const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function cleanText(raw: string): string {
  if (!raw) return '';
  return raw
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .replace(/\t/g, ' ')
    .replace(/[ \u00A0\u1680\u2000-\u200B\u202F\u205F\u3000]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

export async function extractTextFromPdf(arrayBuffer: ArrayBuffer): Promise<string> {
  try {
    // Dynamic import pdfjs-dist for browser compatibility
    const pdfjsLib = await import('pdfjs-dist');
    // Ensure worker is configured or disabled for standalone text extraction
    if (!pdfjsLib.GlobalWorkerOptions.workerSrc) {
      pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;
    }

    const loadingTask = pdfjsLib.getDocument({ data: new Uint8Array(arrayBuffer) });
    const pdfDoc = await loadingTask.promise;
    const pagesText: string[] = [];

    for (let pageNum = 1; pageNum <= pdfDoc.numPages; pageNum++) {
      const page = await pdfDoc.getPage(pageNum);
      const textContent = await page.getTextContent();
      const pageStrings = textContent.items
        .map((item: any) => item.str || '')
        .filter(Boolean);
      pagesText.push(pageStrings.join(' '));
    }

    return pagesText.join('\n\n');
  } catch (err: any) {
    if (err?.name === 'PasswordException' || String(err).toLowerCase().includes('password')) {
      throw new Error('PDF is password-protected or encrypted.');
    }
    throw new Error(`PDF extraction failed: ${err.message || err}`);
  }
}

export async function extractTextFromDocx(arrayBuffer: ArrayBuffer): Promise<string> {
  try {
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value || '';
  } catch (err: any) {
    throw new Error(`DOCX extraction failed: ${err.message || err}`);
  }
}

export async function processFile(
  file: File,
  seenHashes: Set<string>
): Promise<DocumentResult> {
  const filename = file.name;
  const lowerName = filename.toLowerCase();

  // Extension check
  const isPdf = lowerName.endsWith('.pdf');
  const isDocx = lowerName.endsWith('.docx');
  const isTxt = lowerName.endsWith('.txt');

  if (!isPdf && !isDocx && !isTxt) {
    return {
      filename,
      status: 'unsupported_format',
      error: `Unsupported file type '${filename}'. Accepted formats: PDF, DOCX, TXT.`,
      text: '',
      char_count: 0,
    };
  }

  // Zero-byte check
  if (file.size === 0) {
    return {
      filename,
      status: 'empty_file',
      error: 'File is empty (0 bytes).',
      text: '',
      char_count: 0,
    };
  }

  // Size limit
  if (file.size > MAX_FILE_SIZE_BYTES) {
    const sizeMb = file.size / (1024 * 1024);
    return {
      filename,
      status: 'file_too_large',
      error: `File is ${sizeMb.toFixed(1)} MB; the limit is 10 MB.`,
      text: '',
      char_count: 0,
    };
  }

  const arrayBuffer = await file.arrayBuffer();

  // Content SHA-256 duplicate detection
  const hash = await computeSha256(arrayBuffer);
  if (seenHashes.has(hash)) {
    return {
      filename,
      status: 'duplicate',
      error: 'A file with identical content has already been processed in this batch.',
      file_hash: hash,
      text: '',
      char_count: 0,
    };
  }

  // Extraction
  let rawText = '';
  try {
    if (isPdf) {
      rawText = await extractTextFromPdf(arrayBuffer);
    } else if (isDocx) {
      rawText = await extractTextFromDocx(arrayBuffer);
    } else {
      rawText = new TextDecoder().decode(arrayBuffer);
    }
  } catch (err: any) {
    const errMsg = err?.message || String(err);
    if (errMsg.toLowerCase().includes('password')) {
      return {
        filename,
        status: 'password_protected',
        error: errMsg,
        file_hash: hash,
        text: '',
        char_count: 0,
      };
    }
    return {
      filename,
      status: 'corrupt',
      error: errMsg,
      file_hash: hash,
      text: '',
      char_count: 0,
    };
  }

  const cleaned = cleanText(rawText);

  // Check if text is too short or empty (e.g. scanned image PDF)
  if (cleaned.length < MIN_TEXT_CHARS) {
    return {
      filename,
      status: 'empty',
      error: 'No readable text could be extracted. The file may be a scanned image or contain only graphics.',
      file_hash: hash,
      text: cleaned,
      char_count: cleaned.length,
    };
  }

  return {
    filename,
    status: 'success',
    text: cleaned,
    file_hash: hash,
    char_count: cleaned.length,
  };
}
