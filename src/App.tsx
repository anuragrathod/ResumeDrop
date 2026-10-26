import React, { useState, useEffect, useRef, useId } from 'react';
import {
  FileText,
  Upload,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RotateCcw,
  Download,
  Trash2,
  Edit3,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  Database,
  BarChart2,
  Eye,
  FileCode,
  Sparkles,
  Layers,
  Check,
  AlertCircle
} from 'lucide-react';
import {
  CandidateRecord,
  DocumentResult,
  EducationRecord,
  FailedDocument,
  Project,
  WorkExperience,
} from './types/candidate';
import { processFile } from './services/documentReader';
import {
  cleanEducation,
  cleanLocation,
  cleanName,
  cleanPhone,
  cleanProject,
  cleanSkillsList,
  cleanUrl,
  cleanWorkExperience,
  mergeResults,
  runRuleBasedExtraction,
} from './services/ruleExtractor';
import { validateCandidate } from './services/validator';
import { generateExcelWorkbook } from './services/excelExporter';
import { SAMPLE_DATASET } from './data/sampleDataset';

type TabType = 'main' | 'viewer' | 'benchmark';

interface ModelOption {
  id: string;
  name: string;
  provider: string;
}

const DEFAULT_MODELS: ModelOption[] = [
  { id: 'gemini-3.8-flash', name: 'Gemini 3.8 Flash (Ultra-fast & Accurate)', provider: 'gemini' },
  { id: 'gemini-3.1-flash-lite', name: 'Gemini 3.1 Flash Lite (High-Speed)', provider: 'gemini' },
  { id: 'openai/gpt-oss-120b', name: 'Groq: GPT-OSS 120B', provider: 'groq' },
  { id: 'openai/gpt-oss-20b', name: 'Groq: GPT-OSS 20B', provider: 'groq' },
  { id: 'qwen/qwen3.8-27b', name: 'Groq: Qwen 3.8 27B', provider: 'groq' },
  { id: 'rules_only', name: 'Rules-Only Mode (Offline / Regex)', provider: 'rules_only' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('main');
  const [selectedModel, setSelectedModel] = useState<string>('gemini-3.8-flash');
  const [availableModels, setAvailableModels] = useState<ModelOption[]>(DEFAULT_MODELS);
  const [aiStatus, setAiStatus] = useState<{ gemini_available: boolean; groq_available: boolean; active_engine: string }>({
    gemini_available: true,
    groq_available: false,
    active_engine: 'gemini',
  });
  const [customGroqKey, setCustomGroqKey] = useState<string>('');
  const [showKeyModal, setShowKeyModal] = useState<boolean>(false);

  // Files & Processing
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [progressPercent, setProgressPercent] = useState<number>(0);
  const [currentProgressText, setCurrentProgressText] = useState<string>('');
  const [progressLogs, setProgressLogs] = useState<{ ok: boolean; message: string }[]>([]);

  // Extracted Data
  const [candidates, setCandidates] = useState<CandidateRecord[]>([]);
  const [failedDocs, setFailedDocs] = useState<FailedDocument[]>([]);
  const [isProcessed, setIsProcessed] = useState<boolean>(false);
  const [expandedCandidates, setExpandedCandidates] = useState<Record<string, boolean>>({});
  const [savedNotifications, setSavedNotifications] = useState<Record<string, string>>({});

  // Extracted Text Viewer state (/e)
  const [viewerFile, setViewerFile] = useState<File | null>(null);
  const [viewerResult, setViewerResult] = useState<DocumentResult | null>(null);
  const [isExtractingViewer, setIsExtractingViewer] = useState<boolean>(false);

  // Benchmark state
  const [benchmarkRunning, setBenchmarkRunning] = useState<boolean>(false);
  const [benchmarkResults, setBenchmarkResults] = useState<any[]>([]);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const viewerInputRef = useRef<HTMLInputElement>(null);

  // Fetch backend status on mount
  useEffect(() => {
    fetch('/api/status')
      .then((res) => res.json())
      .then((data) => {
        if (data.models) setAvailableModels(data.models);
        setAiStatus({
          gemini_available: data.gemini_available,
          groq_available: data.groq_available,
          active_engine: data.active_engine,
        });
        if (!data.gemini_available && data.groq_available) {
          setSelectedModel('openai/gpt-oss-120b');
        } else if (!data.gemini_available && !data.groq_available) {
          setSelectedModel('rules_only');
        }
      })
      .catch(() => {
        // Dev fallback
      });
  }, []);

  const handleResetWorkspace = () => {
    setUploadedFiles([]);
    setCandidates([]);
    setFailedDocs([]);
    setIsProcessed(false);
    setProgressPercent(0);
    setProgressLogs([]);
    setExpandedCandidates({});
    setSavedNotifications({});
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      addFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      addFiles(Array.from(e.target.files));
    }
  };

  const addFiles = (newFiles: File[]) => {
    const valid = newFiles.filter((f) => {
      const ext = f.name.toLowerCase();
      return ext.endsWith('.pdf') || ext.endsWith('.docx') || ext.endsWith('.txt');
    });
    setUploadedFiles((prev) => [...prev, ...valid]);
    if (isProcessed) {
      setIsProcessed(false);
      setCandidates([]);
      setFailedDocs([]);
    }
  };

  const loadSampleResume = (sampleId: string) => {
    const item = SAMPLE_DATASET.find((s) => s.id === sampleId);
    if (!item) return;
    const blob = new Blob([item.text], { type: 'text/plain' });
    const file = new File([blob], `${item.expected.full_name?.toLowerCase().replace(/\s+/g, '_') || item.id}_resume.txt`, {
      type: 'text/plain',
    });
    addFiles([file]);
  };

  const loadAllSamples = () => {
    const files = SAMPLE_DATASET.map((item) => {
      const blob = new Blob([item.text], { type: 'text/plain' });
      return new File([blob], `${item.expected.full_name?.toLowerCase().replace(/\s+/g, '_') || item.id}_resume.txt`, {
        type: 'text/plain',
      });
    });
    addFiles(files);
  };

  // Duplicate detection in current uploads
  const duplicateNames = React.useMemo(() => {
    const counts = new Map<string, number>();
    uploadedFiles.forEach((f) => {
      counts.set(f.name, (counts.get(f.name) || 0) + 1);
    });
    const dupes: string[] = [];
    counts.forEach((count, name) => {
      if (count > 1) dupes.push(name);
    });
    return dupes;
  }, [uploadedFiles]);

  // Main processing pipeline
  const processResumes = async () => {
    if (uploadedFiles.length === 0 || isProcessing) return;

    setIsProcessing(true);
    setProgressPercent(0);
    setProgressLogs([]);
    setCurrentProgressText('Starting resume extraction...');

    // Deduplicate uploads by name as in original app
    const seenNames = new Set<string>();
    const uniqueFiles: File[] = [];
    for (const f of uploadedFiles) {
      if (!seenNames.has(f.name)) {
        seenNames.add(f.name);
        uniqueFiles.push(f);
      }
    }

    const total = uniqueFiles.length;
    const newCandidates: CandidateRecord[] = [];
    const newFailedDocs: FailedDocument[] = [];
    const seenHashes = new Set<string>();

    for (let i = 0; i < total; i++) {
      const file = uniqueFiles[i];
      const pct = Math.round(((i) / total) * 100);
      setProgressPercent(pct);
      setCurrentProgressText(`Processing ${file.name} (${i + 1}/${total})...`);

      try {
        // Step 1: Read document (PDF/DOCX/TXT)
        const docResult = await processFile(file, seenHashes);
        if (docResult.file_hash) seenHashes.add(docResult.file_hash);

        if (docResult.status === 'success') {
          const rawText = docResult.text;

          // Step 2: Rule-based extraction
          const ruleData = runRuleBasedExtraction(rawText);

          let aiData: Record<string, any> = {};
          let extractionMethod: 'rules_only' | 'ai' | 'rules+ai' = 'rules_only';
          let modelUsed: string | null = null;
          let aiError: string | null = null;

          // Step 3: AI extraction if not rules_only mode
          if (selectedModel !== 'rules_only') {
            try {
              const res = await fetch('/api/extract', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  text: rawText,
                  filename: file.name,
                  model: selectedModel,
                  customApiKey: customGroqKey || undefined,
                }),
              });
              const aiResponse = await res.json();
              if (aiResponse.success && aiResponse.data) {
                aiData = aiResponse.data;
                extractionMethod = 'rules+ai';
                modelUsed = aiResponse.model_used || selectedModel;
              } else if (aiResponse.error) {
                aiError = aiResponse.error;
              }
            } catch (err: any) {
              aiError = err?.message || String(err);
            }
          }

          // Step 4: Merge results with strict precedence
          const merged = mergeResults(ruleData, aiData);

          // Build candidate record
          const eduList = (merged.education || []).map((e: any) =>
            cleanEducation({
              qualification: e.qualification || null,
              specialization: e.specialization || null,
              institution: e.institution || null,
              start_year: e.start_year ? String(e.start_year) : null,
              graduation_year: e.graduation_year ? String(e.graduation_year) : null,
            })
          );

          const expList = (merged.work_experience || []).map((e: any) =>
            cleanWorkExperience({
              employer: e.employer || null,
              job_title: e.job_title || null,
              start_date: e.start_date || null,
              end_date: e.end_date || null,
              summary: e.summary || null,
              responsibilities: Array.isArray(e.responsibilities) ? e.responsibilities : [],
              description: e.description || null,
            })
          );

          const projList = (merged.projects || []).map((p: any) =>
            cleanProject({
              name: p.name || null,
              summary: p.summary || null,
              description: p.description || null,
              technologies: Array.isArray(p.technologies) ? p.technologies : [],
            })
          );

          let candidate: CandidateRecord = {
            candidate_id: crypto.randomUUID().slice(0, 8),
            resume_filename: file.name,
            full_name: cleanName(merged.full_name),
            email: merged.email ? String(merged.email).trim().toLowerCase() : null,
            phone: cleanPhone(merged.phone),
            location: cleanLocation(merged.location),
            education: eduList,
            technical_skills: cleanSkillsList(merged.technical_skills || []),
            programming_languages: cleanSkillsList(merged.programming_languages || []),
            tools: cleanSkillsList(merged.tools || []),
            work_experience: expList,
            projects: projList,
            certifications: cleanSkillsList(merged.certifications || []),
            linkedin_url: cleanUrl(merged.linkedin_url),
            github_url: cleanUrl(merged.github_url),
            portfolio_url: cleanUrl(merged.portfolio_url),
            metadata: {
              processing_status: 'success',
              missing_fields: [],
              validation_issues: [],
              review_notes: merged._conflicts || [],
              extraction_method: extractionMethod,
              model_used: modelUsed,
              extracted_at: new Date().toISOString(),
            },
            raw_text_snippet: rawText.slice(0, 500),
          };

          if (aiError) {
            candidate.metadata.validation_issues.push(`AI extraction failed: ${aiError}`);
            candidate.metadata.processing_status = 'partial';
          }

          // Step 5: Post-extraction validation
          candidate = validateCandidate(candidate);
          newCandidates.push(candidate);

          setProgressLogs((prev) => [
            ...prev,
            { ok: true, message: `✓ ${file.name} → ${candidate.metadata.processing_status}` },
          ]);
        } else {
          newFailedDocs.push({
            filename: file.name,
            doc_status: docResult.status,
            error: docResult.error,
            char_count: docResult.char_count,
          });
          setProgressLogs((prev) => [
            ...prev,
            { ok: false, message: `✗ ${file.name} → ${docResult.error}` },
          ]);
        }
      } catch (err: any) {
        newFailedDocs.push({
          filename: file.name,
          doc_status: 'error',
          error: err?.message || String(err),
          char_count: 0,
        });
        setProgressLogs((prev) => [
          ...prev,
          { ok: false, message: `✗ ${file.name} → Unexpected error: ${err?.message || err}` },
        ]);
      }
    }

    setProgressPercent(100);
    setCurrentProgressText('Extraction complete');
    setCandidates(newCandidates);
    setFailedDocs(newFailedDocs);
    setIsProcessed(true);
    setIsProcessing(false);

    // Expand first review_required candidate by default
    const firstReview = newCandidates.find((c) => c.metadata.processing_status === 'review_required');
    if (firstReview) {
      setExpandedCandidates({ [firstReview.resume_filename]: true });
    }
  };

  // Download Excel Workbook (.xlsx)
  const handleDownloadExcel = async () => {
    try {
      const blob = await generateExcelWorkbook(candidates, failedDocs);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      const timestamp = new Date()
        .toISOString()
        .replace(/[-:]/g, '')
        .replace('T', '_')
        .slice(0, 15);
      a.href = url;
      a.download = `candidates_${timestamp}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(`Error generating Excel file: ${err?.message || err}`);
    }
  };

  // Download JSON
  const handleDownloadJson = () => {
    const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(candidates, null, 2));
    const a = document.createElement('a');
    a.href = dataStr;
    a.download = `candidates_${Date.now()}.json`;
    a.click();
  };

  // Save changes from candidate inline editor
  const handleSaveCandidateEdit = (filename: string, updatedRecord: CandidateRecord) => {
    const validated = validateCandidate(updatedRecord);
    setCandidates((prev) => prev.map((c) => (c.resume_filename === filename ? validated : c)));
    setSavedNotifications((prev) => ({ ...prev, [filename]: 'Saved successfully!' }));
    setTimeout(() => {
      setSavedNotifications((prev) => {
        const next = { ...prev };
        delete next[filename];
        return next;
      });
    }, 3000);
  };

  // Extracted text viewer handler
  const handleViewerUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setViewerFile(file);
    setIsExtractingViewer(true);
    try {
      const res = await processFile(file, new Set());
      setViewerResult(res);
    } catch (err: any) {
      setViewerResult({
        filename: file.name,
        status: 'error',
        text: '',
        error: err?.message || String(err),
        char_count: 0,
      });
    } finally {
      setIsExtractingViewer(false);
    }
  };

  const downloadViewerTxt = () => {
    if (!viewerResult || !viewerResult.text) return;
    const blob = new Blob([viewerResult.text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const baseName = viewerResult.filename.replace(/\.[^/.]+$/, '');
    a.href = url;
    a.download = `${baseName}_extracted.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Run benchmark against synthetic dataset
  const runBenchmark = async () => {
    setBenchmarkRunning(true);
    const results = [];
    for (const item of SAMPLE_DATASET) {
      const startTime = performance.now();
      const rules = runRuleBasedExtraction(item.text);
      let aiOut: any = {};
      let errStr = '';

      if (selectedModel !== 'rules_only') {
        try {
          const resp = await fetch('/api/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              text: item.text,
              filename: `${item.id}.txt`,
              model: selectedModel,
              customApiKey: customGroqKey || undefined,
            }),
          });
          const json = await resp.json();
          if (json.success) aiOut = json.data;
          else errStr = json.error || 'Failed';
        } catch (e: any) {
          errStr = e?.message || 'Error';
        }
      }

      const merged = mergeResults(rules, aiOut);
      const duration = ((performance.now() - startTime) / 1000).toFixed(2);

      // Evaluate match against ground truth
      const exp = item.expected;
      const nameMatch = cleanName(merged.full_name) === exp.full_name;
      const emailMatch = (merged.email || '').toLowerCase() === (exp.email || '').toLowerCase();
      const phoneDigits = (merged.phone || '').replace(/\D/g, '');
      const expPhoneDigits = (exp.phone || '').replace(/\D/g, '');
      const phoneMatch = phoneDigits === expPhoneDigits;
      const locMatch = Boolean(merged.location);

      results.push({
        id: item.id,
        notes: item.notes,
        duration: `${duration}s`,
        name: { actual: cleanName(merged.full_name) || 'None', expected: exp.full_name, pass: nameMatch },
        email: { actual: merged.email || 'None', expected: exp.email, pass: emailMatch },
        phone: { actual: merged.phone || 'None', expected: exp.phone, pass: phoneMatch },
        location: { actual: merged.location || 'None', expected: exp.location, pass: locMatch },
        educationCount: { actual: (merged.education || []).length, expected: exp.education_count },
        experienceCount: { actual: (merged.work_experience || []).length, expected: exp.work_experience_count },
        projectCount: { actual: (merged.projects || []).length, expected: exp.project_count },
        error: errStr,
      });
    }
    setBenchmarkResults(results);
    setBenchmarkRunning(false);
  };

  // Metrics summary
  const totalResumes = candidates.length + failedDocs.length;
  const verifiedCount = candidates.filter((c) => c.metadata.processing_status === 'success').length;
  const reviewCount = candidates.filter(
    (c) => c.metadata.processing_status === 'review_required' || c.metadata.processing_status === 'partial'
  ).length;
  const failedCount = failedDocs.length;

  return (
    <div className="min-h-screen bg-[#fbfbfd] text-[#1d1d1f] flex flex-col md:flex-row">
      {/* ------------------------------------------------------------- */}
      {/* Sidebar (Matching Streamlit sidebar architecture)             */}
      {/* ------------------------------------------------------------- */}
      <aside className="w-full md:w-72 bg-[#f5f5f7] border-r border-black/10 flex flex-col p-5 shrink-0">
        <div className="flex items-center gap-2 mb-6">
          <div className="w-8 h-8 rounded-lg bg-[#0071e3] text-white flex items-center justify-center font-bold text-lg shadow-sm">
            📄
          </div>
          <span className="text-xl font-bold tracking-tight text-[#1d1d1f]">ResumeDrop</span>
        </div>

        {/* Navigation tabs */}
        <div className="space-y-1 mb-6">
          <button
            onClick={() => setActiveTab('main')}
            className={`w-full text-left px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2.5 ${
              activeTab === 'main'
                ? 'bg-white text-[#0071e3] shadow-sm font-semibold'
                : 'text-[#6e6e73] hover:text-[#1d1d1f] hover:bg-black/5'
            }`}
          >
            <Layers className="w-4 h-4" />
            Resume to Excel
          </button>
          <button
            onClick={() => setActiveTab('viewer')}
            className={`w-full text-left px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2.5 ${
              activeTab === 'viewer'
                ? 'bg-white text-[#0071e3] shadow-sm font-semibold'
                : 'text-[#6e6e73] hover:text-[#1d1d1f] hover:bg-black/5'
            }`}
          >
            <Eye className="w-4 h-4" />
            Extracted text (/e)
          </button>
          <button
            onClick={() => setActiveTab('benchmark')}
            className={`w-full text-left px-3.5 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2.5 ${
              activeTab === 'benchmark'
                ? 'bg-white text-[#0071e3] shadow-sm font-semibold'
                : 'text-[#6e6e73] hover:text-[#1d1d1f] hover:bg-black/5'
            }`}
          >
            <BarChart2 className="w-4 h-4" />
            Accuracy Benchmark
          </button>
        </div>

        <div className="border-t border-black/10 pt-4 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-[#6e6e73] uppercase tracking-wider mb-1.5">
              AI Engine & Model
            </label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-white border border-black/15 rounded-lg px-3 py-2 text-sm text-[#1d1d1f] focus:outline-none focus:border-[#0071e3] shadow-sm cursor-pointer"
            >
              {availableModels.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.name}
                </option>
              ))}
            </select>
          </div>

          {/* Connection status indicator */}
          <div className="bg-white/80 border border-black/10 rounded-lg p-3 text-xs space-y-1.5">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  selectedModel === 'rules_only'
                    ? 'bg-[#b25000]'
                    : aiStatus.gemini_available || aiStatus.groq_available || customGroqKey
                    ? 'bg-[#248a3d]'
                    : 'bg-[#b25000]'
                }`}
              />
              <span className="font-medium text-[#1d1d1f]">
                {selectedModel === 'rules_only'
                  ? 'Rules-only mode active'
                  : selectedModel.startsWith('gemini')
                  ? aiStatus.gemini_available
                    ? 'Gemini Cloud AI Connected'
                    : 'Gemini (Auto-fallback mode)'
                  : aiStatus.groq_available || customGroqKey
                  ? 'Groq Cloud LPU Connected'
                  : 'Groq key required'}
              </span>
            </div>
            <p className="text-[#6e6e73] text-[11px] leading-relaxed">
              {selectedModel === 'rules_only'
                ? '100% offline regex extraction for email, phone, and profile links.'
                : selectedModel.startsWith('gemini')
                ? 'Deep parsing for multi-entry education, jobs, projects & all skills.'
                : 'High-speed cloud LPU extraction.'}
            </p>
          </div>

          {/* Sample Resumes Loader */}
          <div className="pt-2">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-[#6e6e73] uppercase tracking-wider">
                Sample Resumes
              </span>
              <button
                onClick={loadAllSamples}
                className="text-[11px] text-[#0071e3] hover:underline font-medium"
              >
                Load all 5
              </button>
            </div>
            <div className="space-y-1">
              {SAMPLE_DATASET.slice(0, 4).map((s) => (
                <button
                  key={s.id}
                  onClick={() => loadSampleResume(s.id)}
                  className="w-full text-left px-2.5 py-1.5 bg-white border border-black/5 hover:border-[#0071e3]/40 rounded-md text-xs text-[#1d1d1f] truncate transition-colors flex items-center justify-between"
                  title={s.notes}
                >
                  <span className="truncate">{s.expected.full_name}</span>
                  <span className="text-[10px] text-[#6e6e73] font-mono shrink-0 ml-1">
                    {s.id.split('_')[1]}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Groq Key Option if using Groq */}
          {selectedModel.includes('gpt-oss') || selectedModel.includes('qwen') ? (
            <div className="pt-1">
              <button
                onClick={() => setShowKeyModal(true)}
                className="text-xs text-[#0071e3] hover:underline flex items-center gap-1 font-medium"
              >
                <span>⚙ Configure Groq API Key</span>
              </button>
            </div>
          ) : null}
        </div>

        <div className="mt-auto pt-6 border-t border-black/10">
          <button
            onClick={handleResetWorkspace}
            className="w-full py-2 px-3 border border-black/20 hover:bg-black/5 active:bg-black/10 rounded-full text-xs font-medium text-[#1d1d1f] transition-colors flex items-center justify-center gap-1.5"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset workspace
          </button>
        </div>
      </aside>

      {/* ------------------------------------------------------------- */}
      {/* Main Content Area                                             */}
      {/* ------------------------------------------------------------- */}
      <main className="flex-1 overflow-y-auto p-4 sm:p-8 max-w-5xl mx-auto w-full">
        {/* Tab 1: Main "Resume to Excel" App */}
        {activeTab === 'main' && (
          <div className="space-y-8">
            {/* Header */}
            <div>
              <h1 className="text-3xl sm:text-4xl font-bold tracking-tight text-[#1d1d1f]">
                Resume to Excel
              </h1>
              <p className="mt-2 text-base text-[#6e6e73] max-w-2xl leading-relaxed">
                Drop PDF or DOCX resumes below. Candidate details are extracted into a formatted Excel
                workbook with 5 worksheets you can review and edit first.
              </p>
            </div>

            {/* Upload Box */}
            <div
              onDragOver={(e) => e.preventDefault()}
              onDrop={handleFileDrop}
              onClick={() => fileInputRef.current?.click()}
              className="group border-2 border-dashed border-black/20 hover:border-[#0071e3] bg-white rounded-2xl p-8 sm:p-10 text-center cursor-pointer transition-all duration-200 shadow-sm hover:shadow-md"
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.txt"
                onChange={handleFileInput}
                className="hidden"
              />
              <div className="w-12 h-12 rounded-full bg-[#0071e3]/10 text-[#0071e3] flex items-center justify-center mx-auto mb-3.5 group-hover:scale-105 transition-transform">
                <Upload className="w-6 h-6" />
              </div>
              <h3 className="text-base font-semibold text-[#1d1d1f]">
                Drop PDF, DOCX, or TXT resumes here
              </h3>
              <p className="text-xs text-[#6e6e73] mt-1">
                Drag-and-drop multiple files or click to browse. Up to 10 MB per file.
              </p>
            </div>

            {/* Uploaded File Chips */}
            {uploadedFiles.length > 0 && (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2">
                  {uploadedFiles.map((f, idx) => {
                    const isDup = duplicateNames.includes(f.name);
                    const sizeKb = (f.size / 1024).toFixed(1);
                    return (
                      <div
                        key={`${f.name}-${idx}`}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs bg-white border ${
                          isDup ? 'border-[#b25000]/60 text-[#b25000]' : 'border-black/15 text-[#1d1d1f]'
                        } shadow-xs`}
                      >
                        <FileText className="w-3.5 h-3.5 opacity-60" />
                        <span className="font-medium truncate max-w-[180px]">{f.name}</span>
                        <span className="text-[#6e6e73] text-[11px]">
                          {sizeKb} KB {isDup && '· duplicate'}
                        </span>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setUploadedFiles((prev) => prev.filter((_, i) => i !== idx));
                          }}
                          className="hover:text-red-500 ml-1 text-black/40"
                        >
                          ×
                        </button>
                      </div>
                    );
                  })}
                </div>

                {duplicateNames.length > 0 && (
                  <div className="bg-[#b25000]/10 border border-[#b25000]/25 rounded-xl p-3 text-xs text-[#b25000] flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                    <span>
                      Duplicate files detected: <strong>{duplicateNames.join(', ')}</strong>.
                      Content hash deduplication will process duplicate files once.
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Action Bar */}
            <div className="flex items-center gap-3 pt-1">
              <button
                onClick={processResumes}
                disabled={uploadedFiles.length === 0 || isProcessing}
                className="px-6 py-2.5 rounded-full font-medium text-sm bg-[#0071e3] hover:bg-[#0077ed] text-white disabled:bg-black/10 disabled:text-[#6e6e73] disabled:cursor-not-allowed shadow-sm transition-all"
              >
                {isProcessing ? 'Processing resumes...' : '▶ Process resumes'}
              </button>
              <button
                onClick={handleResetWorkspace}
                disabled={uploadedFiles.length === 0 && candidates.length === 0}
                className="px-5 py-2.5 rounded-full font-medium text-sm bg-white border border-black/20 hover:bg-black/5 text-[#1d1d1f] disabled:opacity-40 disabled:cursor-not-allowed transition-all"
              >
                Clear all
              </button>
            </div>

            {/* Live Progress Bar */}
            {isProcessing && (
              <div className="space-y-3 bg-white p-5 rounded-xl border border-black/10 shadow-xs">
                <div className="flex justify-between text-xs font-medium text-[#1d1d1f]">
                  <span>{currentProgressText}</span>
                  <span>{progressPercent}%</span>
                </div>
                <div className="w-full bg-black/5 rounded-full h-2 overflow-hidden">
                  <div
                    className="bg-[#0071e3] h-full rounded-full transition-all duration-300"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
                {progressLogs.length > 0 && (
                  <div className="max-h-24 overflow-y-auto text-xs font-mono space-y-1 pt-1">
                    {progressLogs.slice(-4).map((log, i) => (
                      <div
                        key={i}
                        className={log.ok ? 'text-[#248a3d]' : 'text-[#d70015]'}
                      >
                        {log.message}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Results Section */}
            {isProcessed && (
              <div className="space-y-8 pt-4">
                <div className="border-t border-black/10 pt-6">
                  <h2 className="text-2xl font-bold tracking-tight text-[#1d1d1f]">Results</h2>
                </div>

                {/* 4 Apple-style Plain Metrics Figures */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-6 border-b border-black/10 pb-6">
                  <div className="border-t border-black/10 pt-3">
                    <div className="text-xs font-medium text-[#6e6e73]">Total resumes</div>
                    <div className="text-3xl font-semibold tracking-tight text-[#1d1d1f] mt-1">
                      {totalResumes}
                    </div>
                  </div>
                  <div className="border-t border-black/10 pt-3">
                    <div className="text-xs font-medium text-[#6e6e73]">Verified</div>
                    <div className="text-3xl font-semibold tracking-tight text-[#248a3d] mt-1">
                      {verifiedCount}
                    </div>
                  </div>
                  <div className="border-t border-black/10 pt-3">
                    <div className="text-xs font-medium text-[#6e6e73]">Needs review</div>
                    <div className="text-3xl font-semibold tracking-tight text-[#b25000] mt-1">
                      {reviewCount}
                    </div>
                  </div>
                  <div className="border-t border-black/10 pt-3">
                    <div className="text-xs font-medium text-[#6e6e73]">Failed</div>
                    <div className="text-3xl font-semibold tracking-tight text-[#d70015] mt-1">
                      {failedCount}
                    </div>
                  </div>
                </div>

                {/* Candidates Overview Table */}
                {candidates.length > 0 && (
                  <div className="space-y-3">
                    <div className="overflow-x-auto rounded-xl border border-black/10 bg-white shadow-xs">
                      <table className="w-full text-left text-xs border-collapse">
                        <thead>
                          <tr className="bg-[#f5f5f7] border-b border-black/10 text-[#6e6e73] font-semibold">
                            <th className="py-3 px-3.5">Filename</th>
                            <th className="py-3 px-3.5">Candidate Name</th>
                            <th className="py-3 px-3.5">Email</th>
                            <th className="py-3 px-3.5">Phone</th>
                            <th className="py-3 px-3.5">Education</th>
                            <th className="py-3 px-3.5">Top Skills</th>
                            <th className="py-3 px-3.5">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-black/5 text-[#1d1d1f]">
                          {candidates.map((c) => {
                            const eduStr = c.education
                              .map((e) => [e.qualification, e.institution, e.graduation_year].filter(Boolean).join(' · '))
                              .join('; ');
                            const topSkills = c.technical_skills.slice(0, 4).join(', ');
                            const status = c.metadata.processing_status;

                            let badge = 'bg-black/10 text-[#1d1d1f]';
                            let label = 'Pending';
                            if (status === 'success') {
                              badge = 'bg-[#248a3d]/15 text-[#248a3d] border border-[#248a3d]/30 font-medium';
                              label = 'Verified';
                            } else if (status === 'review_required') {
                              badge = 'bg-[#b25000]/15 text-[#b25000] border border-[#b25000]/30 font-medium';
                              label = 'Needs Review';
                            } else if (status === 'partial') {
                              badge = 'bg-[#b25000]/15 text-[#b25000] border border-[#b25000]/30 font-medium';
                              label = 'Partial';
                            } else if (status === 'failed') {
                              badge = 'bg-[#d70015]/15 text-[#d70015] border border-[#d70015]/30 font-medium';
                              label = 'Failed';
                            }

                            return (
                              <tr key={c.candidate_id} className="hover:bg-[#fbfbfd]">
                                <td className="py-3 px-3.5 font-medium">{c.resume_filename}</td>
                                <td className="py-3 px-3.5">{c.full_name || '—'}</td>
                                <td className="py-3 px-3.5 font-mono">{c.email || '—'}</td>
                                <td className="py-3 px-3.5">{c.phone || '—'}</td>
                                <td className="py-3 px-3.5 max-w-[200px] truncate" title={eduStr}>
                                  {eduStr || '—'}
                                </td>
                                <td className="py-3 px-3.5 max-w-[180px] truncate" title={topSkills}>
                                  {topSkills || '—'}
                                </td>
                                <td className="py-3 px-3.5">
                                  <span className={`px-2 py-0.5 rounded-full text-[11px] ${badge}`}>
                                    {label}
                                  </span>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}

                {/* Failed Documents List */}
                {failedDocs.length > 0 && (
                  <div className="bg-[#d70015]/5 border border-[#d70015]/20 rounded-xl p-4 space-y-2">
                    <h3 className="text-xs font-bold uppercase text-[#d70015] tracking-wide">
                      Failed Documents ({failedDocs.length})
                    </h3>
                    <ul className="text-xs text-[#1d1d1f] space-y-1.5 list-disc list-inside">
                      {failedDocs.map((fd, i) => (
                        <li key={i}>
                          <strong>{fd.filename}</strong> — <code className="text-[#d70015]">{fd.doc_status}</code>:{' '}
                          {fd.error || 'Unspecified error'}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Inline Review and Edit Accordions */}
                {candidates.length > 0 && (
                  <div className="space-y-4 pt-4">
                    <div>
                      <h3 className="text-xl font-bold tracking-tight text-[#1d1d1f]">
                        Review and edit
                      </h3>
                      <p className="text-xs text-[#6e6e73] mt-1">
                        Changes you save here are automatically re-validated and included in the exported workbook.
                      </p>
                    </div>

                    <div className="space-y-3">
                      {candidates.map((cand) => {
                        const filename = cand.resume_filename;
                        const isExpanded = Boolean(expandedCandidates[filename]);
                        const status = cand.metadata.processing_status;

                        return (
                          <div
                            key={cand.candidate_id}
                            className="bg-white border border-black/10 rounded-xl shadow-xs overflow-hidden transition-all"
                          >
                            <button
                              type="button"
                              onClick={() =>
                                setExpandedCandidates((prev) => ({
                                  ...prev,
                                  [filename]: !prev[filename],
                                }))
                              }
                              className="w-full text-left px-5 py-4 flex items-center justify-between hover:bg-[#fafafc] transition-colors"
                            >
                              <div className="flex items-center gap-3">
                                {isExpanded ? (
                                  <ChevronDown className="w-4 h-4 text-[#6e6e73]" />
                                ) : (
                                  <ChevronRight className="w-4 h-4 text-[#6e6e73]" />
                                )}
                                <span className="font-semibold text-sm text-[#1d1d1f]">
                                  {cand.full_name || filename}
                                </span>
                                <span className="text-xs text-[#6e6e73]">· {filename}</span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span
                                  className={`text-[11px] px-2 py-0.5 rounded-full font-medium ${
                                    status === 'success'
                                      ? 'bg-[#248a3d]/15 text-[#248a3d]'
                                      : 'bg-[#b25000]/15 text-[#b25000]'
                                  }`}
                                >
                                  {status === 'success' ? 'Verified' : 'Needs Review'}
                                </span>
                              </div>
                            </button>

                            {isExpanded && (
                              <div className="p-5 border-t border-black/10 bg-[#fbfbfd] space-y-5">
                                {/* Validation Warnings */}
                                {cand.metadata.validation_issues.length > 0 && (
                                  <div className="bg-[#b25000]/10 border border-[#b25000]/20 rounded-lg p-3 text-xs text-[#b25000] space-y-1">
                                    <div className="font-semibold flex items-center gap-1.5">
                                      <AlertTriangle className="w-3.5 h-3.5" />
                                      Validation Notes:
                                    </div>
                                    <ul className="list-disc list-inside space-y-0.5">
                                      {cand.metadata.validation_issues.map((iss, idx) => (
                                        <li key={idx}>{iss}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {cand.metadata.missing_fields.length > 0 && (
                                  <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3 text-xs text-blue-700">
                                    <strong>Missing Recommended Fields:</strong>{' '}
                                    {cand.metadata.missing_fields.join(', ')}
                                  </div>
                                )}

                                {/* Candidate Edit Form */}
                                <CandidateEditForm
                                  candidate={cand}
                                  onSave={(updated) => handleSaveCandidateEdit(filename, updated)}
                                  notification={savedNotifications[filename]}
                                />
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Export Section */}
                <div className="border-t border-black/10 pt-6 space-y-3">
                  <h3 className="text-xl font-bold tracking-tight text-[#1d1d1f]">Export</h3>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={handleDownloadExcel}
                      className="px-6 py-2.5 rounded-full font-medium text-sm bg-[#0071e3] hover:bg-[#0077ed] text-white flex items-center gap-2 shadow-sm transition-all"
                    >
                      <Download className="w-4 h-4" />
                      Download Excel workbook ({candidates.length} candidates)
                    </button>
                    <button
                      onClick={handleDownloadJson}
                      className="px-4 py-2.5 rounded-full font-medium text-sm bg-white border border-black/20 hover:bg-black/5 text-[#1d1d1f] flex items-center gap-1.5 transition-all"
                    >
                      <FileCode className="w-4 h-4" />
                      Download JSON
                    </button>
                  </div>
                  <p className="text-xs text-[#6e6e73]">
                    The exported workbook contains 5 formatted worksheets: Candidates, Education, Work Experience,
                    Projects, and Processing Log with frozen headers, wrap text, and color fills.
                  </p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Extracted Text Viewer (/e) */}
        {activeTab === 'viewer' && (
          <div className="space-y-6">
            <div>
              <button
                onClick={() => setActiveTab('main')}
                className="text-xs font-semibold text-[#0071e3] hover:underline mb-2 block"
              >
                ← Back to ResumeDrop
              </button>
              <h1 className="text-3xl font-bold tracking-tight text-[#1d1d1f]">Extracted text</h1>
              <p className="text-sm text-[#6e6e73] mt-1">
                Upload a resume to inspect the exact text extracted from it by DocumentReader.
              </p>
            </div>

            <div
              onClick={() => viewerInputRef.current?.click()}
              className="border-2 border-dashed border-black/20 hover:border-[#0071e3] bg-white rounded-2xl p-6 text-center cursor-pointer transition-all"
            >
              <input
                ref={viewerInputRef}
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleViewerUpload}
                className="hidden"
              />
              <Upload className="w-6 h-6 text-[#0071e3] mx-auto mb-2" />
              <div className="text-sm font-semibold text-[#1d1d1f]">Upload a resume (PDF or DOCX)</div>
              <p className="text-xs text-[#6e6e73] mt-0.5">Click to inspect exact raw extracted text</p>
            </div>

            {isExtractingViewer && (
              <div className="text-center py-6 text-sm text-[#6e6e73]">Extracting text...</div>
            )}

            {viewerResult && (
              <div className="space-y-4">
                {viewerResult.status === 'success' ? (
                  <>
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-black/10">
                      <div>
                        <div className="font-semibold text-sm text-[#1d1d1f]">
                          {viewerResult.filename}
                        </div>
                        <div className="text-xs text-[#6e6e73] mt-0.5">
                          {viewerResult.char_count.toLocaleString()} characters ·{' '}
                          {viewerResult.text.split(/\s+/).filter(Boolean).length.toLocaleString()} words ·{' '}
                          {viewerResult.text.split('\n').length.toLocaleString()} lines
                        </div>
                      </div>
                      <button
                        onClick={downloadViewerTxt}
                        className="px-4 py-2 rounded-full font-medium text-xs bg-[#0071e3] hover:bg-[#0077ed] text-white flex items-center justify-center gap-1.5 transition-all"
                      >
                        <Download className="w-3.5 h-3.5" />
                        Download .txt
                      </button>
                    </div>

                    <div className="bg-white border border-black/10 rounded-xl p-5 overflow-x-auto shadow-xs">
                      <pre className="font-mono text-xs text-[#1f2328] whitespace-pre-wrap leading-relaxed">
                        {viewerResult.text}
                      </pre>
                    </div>
                  </>
                ) : (
                  <div className="bg-[#d70015]/10 border border-[#d70015]/20 rounded-xl p-4 text-xs text-[#d70015]">
                    Failed to extract text from {viewerResult.filename}: {viewerResult.error}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Tab 3: Accuracy Benchmark */}
        {activeTab === 'benchmark' && (
          <div className="space-y-6">
            <div>
              <button
                onClick={() => setActiveTab('main')}
                className="text-xs font-semibold text-[#0071e3] hover:underline mb-2 block"
              >
                ← Back to ResumeDrop
              </button>
              <h1 className="text-3xl font-bold tracking-tight text-[#1d1d1f]">
                Extraction Accuracy Evaluation
              </h1>
              <p className="text-sm text-[#6e6e73] mt-1 max-w-2xl">
                Evaluates field-level extraction accuracy against the synthetic benchmark dataset with known ground truth.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={runBenchmark}
                disabled={benchmarkRunning}
                className="px-6 py-2.5 rounded-full font-medium text-sm bg-[#0071e3] hover:bg-[#0077ed] text-white disabled:opacity-50 transition-all shadow-sm"
              >
                {benchmarkRunning ? 'Running evaluation...' : '▶ Run benchmark (5 resumes)'}
              </button>
              <span className="text-xs text-[#6e6e73]">
                Evaluates Name, Email, Phone, Location, Education, Experience & Projects.
              </span>
            </div>

            {benchmarkResults.length > 0 && (
              <div className="space-y-4">
                <div className="overflow-x-auto rounded-xl border border-black/10 bg-white shadow-xs">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="bg-[#f5f5f7] border-b border-black/10 text-[#6e6e73] font-semibold">
                        <th className="py-3 px-3">Test Case</th>
                        <th className="py-3 px-3">Name</th>
                        <th className="py-3 px-3">Email</th>
                        <th className="py-3 px-3">Phone</th>
                        <th className="py-3 px-3">Location</th>
                        <th className="py-3 px-3">Edu Count</th>
                        <th className="py-3 px-3">Jobs</th>
                        <th className="py-3 px-3">Time</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-black/5 text-[#1d1d1f]">
                      {benchmarkResults.map((r) => (
                        <tr key={r.id} className="hover:bg-[#fbfbfd]">
                          <td className="py-3 px-3 font-medium">
                            {r.id}
                            <div className="text-[10px] text-[#6e6e73]">{r.notes}</div>
                          </td>
                          <td className="py-3 px-3">
                            <span className={r.name.pass ? 'text-[#248a3d]' : 'text-[#d70015]'}>
                              {r.name.pass ? '✓' : '✗'} {r.name.actual}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={r.email.pass ? 'text-[#248a3d]' : 'text-[#d70015]'}>
                              {r.email.pass ? '✓' : '✗'} {r.email.actual}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={r.phone.pass ? 'text-[#248a3d]' : 'text-[#d70015]'}>
                              {r.phone.pass ? '✓' : '✗'} {r.phone.actual}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            <span className={r.location.pass ? 'text-[#248a3d]' : 'text-[#d70015]'}>
                              {r.location.pass ? '✓' : '✗'} {r.location.actual}
                            </span>
                          </td>
                          <td className="py-3 px-3">
                            {r.educationCount.actual} / {r.educationCount.expected}
                          </td>
                          <td className="py-3 px-3">
                            {r.experienceCount.actual} / {r.experienceCount.expected}
                          </td>
                          <td className="py-3 px-3 font-mono text-[#6e6e73]">{r.duration}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </main>

      {/* ------------------------------------------------------------- */}
      {/* Groq Key Configuration Modal                                  */}
      {/* ------------------------------------------------------------- */}
      {showKeyModal && (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-black/10 space-y-4">
            <h3 className="text-lg font-bold text-[#1d1d1f]">Groq Cloud API Key</h3>
            <p className="text-xs text-[#6e6e73] leading-relaxed">
              If running Groq models, paste your free Groq API key from{' '}
              <a
                href="https://console.groq.com/keys"
                target="_blank"
                rel="noreferrer"
                className="text-[#0071e3] underline"
              >
                console.groq.com/keys
              </a>
              . Gemini models run natively on AI Studio without configuration.
            </p>
            <div>
              <input
                type="password"
                placeholder="gsk_..."
                value={customGroqKey}
                onChange={(e) => setCustomGroqKey(e.target.value)}
                className="w-full border border-black/20 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[#0071e3]"
              />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button
                onClick={() => setShowKeyModal(false)}
                className="px-4 py-2 rounded-full border border-black/20 text-xs font-medium hover:bg-black/5"
              >
                Done
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// -------------------------------------------------------------
// Candidate Inline Editor Form
// -------------------------------------------------------------

function CandidateEditForm({
  candidate,
  onSave,
  notification,
}: {
  candidate: CandidateRecord;
  onSave: (updated: CandidateRecord) => void;
  notification?: string;
}) {
  const [name, setName] = useState(candidate.full_name || '');
  const [email, setEmail] = useState(candidate.email || '');
  const [phone, setPhone] = useState(candidate.phone || '');
  const [location, setLocation] = useState(candidate.location || '');
  const [linkedin, setLinkedin] = useState(candidate.linkedin_url || '');
  const [github, setGithub] = useState(candidate.github_url || '');
  const [portfolio, setPortfolio] = useState(candidate.portfolio_url || '');
  const [certs, setCerts] = useState(candidate.certifications.join(', '));
  const [skills, setSkills] = useState(candidate.technical_skills.join(', '));
  const [langs, setLangs] = useState(candidate.programming_languages.join(', '));
  const [tools, setTools] = useState(candidate.tools.join(', '));

  // Multi-line editors formatted with pipe separators as in original app
  const [eduText, setEduText] = useState(
    candidate.education
      .map((e) => [e.qualification, e.specialization, e.institution, e.graduation_year].filter(Boolean).join(' | '))
      .join('\n')
  );

  const [expText, setExpText] = useState(
    candidate.work_experience
      .map((e) => [e.employer, e.job_title, e.start_date, e.end_date].filter(Boolean).join(' | '))
      .join('\n')
  );

  const [projText, setProjText] = useState(
    candidate.projects
      .map((p) => [p.name, p.description, (p.technologies || []).join(', ')].filter(Boolean).join(' | '))
      .join('\n')
  );

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    // Parse education lines
    const parsedEdu: EducationRecord[] = eduText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split('|').map((p) => p.trim());
        return {
          qualification: parts[0] || null,
          specialization: parts[1] || null,
          institution: parts[2] || null,
          graduation_year: parts[3] || null,
        };
      });

    // Parse experience lines
    const parsedExp: WorkExperience[] = expText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split('|').map((p) => p.trim());
        return {
          employer: parts[0] || null,
          job_title: parts[1] || null,
          start_date: parts[2] || null,
          end_date: parts[3] || null,
          responsibilities: [],
        };
      });

    // Parse project lines
    const parsedProj: Project[] = projText
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split('|').map((p) => p.trim());
        const techs = parts[2] ? parts[2].split(',').map((t) => t.trim()).filter(Boolean) : [];
        return {
          name: parts[0] || null,
          description: parts[1] || null,
          technologies: techs,
        };
      });

    const splitCsv = (val: string) =>
      val
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);

    const updated: CandidateRecord = {
      ...candidate,
      full_name: name.trim() || null,
      email: email.trim().toLowerCase() || null,
      phone: phone.trim() || null,
      location: location.trim() || null,
      linkedin_url: linkedin.trim() || null,
      github_url: github.trim() || null,
      portfolio_url: portfolio.trim() || null,
      education: parsedEdu,
      work_experience: parsedExp,
      projects: parsedProj,
      technical_skills: splitCsv(skills),
      programming_languages: splitCsv(langs),
      tools: splitCsv(tools),
      certifications: splitCsv(certs),
    };

    onSave(updated);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Full Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Email</label>
          <input
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f] font-mono"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Phone Number</label>
          <input
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Location</label>
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">
          Education (Qualification | Specialization | Institution | Graduation Year)
        </label>
        <textarea
          rows={3}
          value={eduText}
          onChange={(e) => setEduText(e.target.value)}
          placeholder="B.Tech | Computer Engineering | IIT Madras | 2020"
          className="w-full bg-white border border-black/15 rounded-lg p-2.5 text-xs text-[#1d1d1f] font-mono leading-relaxed"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Technical Skills</label>
          <textarea
            rows={2}
            value={skills}
            onChange={(e) => setSkills(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg p-2 text-xs text-[#1d1d1f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Languages</label>
          <textarea
            rows={2}
            value={langs}
            onChange={(e) => setLangs(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg p-2 text-xs text-[#1d1d1f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Tools & Libraries</label>
          <textarea
            rows={2}
            value={tools}
            onChange={(e) => setTools(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg p-2 text-xs text-[#1d1d1f]"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">
          Work Experience (Employer | Job Title | Start Date | End Date)
        </label>
        <textarea
          rows={3}
          value={expText}
          onChange={(e) => setExpText(e.target.value)}
          placeholder="Infosys Ltd | Software Developer | Aug 2020 | Present"
          className="w-full bg-white border border-black/15 rounded-lg p-2.5 text-xs text-[#1d1d1f] font-mono leading-relaxed"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">
          Projects (Project Name | Description | Technologies)
        </label>
        <textarea
          rows={3}
          value={projText}
          onChange={(e) => setProjText(e.target.value)}
          placeholder="PayGateway | Payment processing microservice | Java, Spring Boot, MySQL"
          className="w-full bg-white border border-black/15 rounded-lg p-2.5 text-xs text-[#1d1d1f] font-mono leading-relaxed"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">LinkedIn</label>
          <input
            type="text"
            value={linkedin}
            onChange={(e) => setLinkedin(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">GitHub</label>
          <input
            type="text"
            value={github}
            onChange={(e) => setGithub(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">Portfolio</label>
          <input
            type="text"
            value={portfolio}
            onChange={(e) => setPortfolio(e.target.value)}
            className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
          />
        </div>
      </div>

      <div>
        <label className="block text-xs font-semibold text-[#1d1d1f] mb-1">
          Certifications (comma-separated)
        </label>
        <input
          type="text"
          value={certs}
          onChange={(e) => setCerts(e.target.value)}
          className="w-full bg-white border border-black/15 rounded-lg px-3 py-1.5 text-xs text-[#1d1d1f]"
        />
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          className="px-5 py-2 rounded-full font-medium text-xs bg-[#0071e3] hover:bg-[#0077ed] text-white shadow-xs transition-colors"
        >
          Save changes
        </button>
        {notification && (
          <span className="text-xs text-[#248a3d] font-medium flex items-center gap-1">
            <Check className="w-3.5 h-3.5" />
            {notification}
          </span>
        )}
      </div>
    </form>
  );
}
