# Missing Information & Action Checklist
## Project: ResumeDrop (AI Resume Extraction & Excel Automation)

This checklist details all non-recoverable pieces of information that cannot be determined exclusively from static inspection of the code repository. These details must be supplied by the project author, development team, or academic supervisor prior to finalizing the bound academic thesis or formal industry technical whitepaper.

---

## 1. Actionable Information Checklist

| Item ID | Missing Information Item | Why It Is Needed | Current Repository Status | How the Project Team Can Obtain It | Report Chapters Affected | Priority |
|---|---|---|---|---|---|---|
| **MIC-01** | **Author & Institutional Metadata** | Title page, Certificate of Authenticity, and Declaration pages require official candidate and academic identifiers. | **Absent from code.** Repository indicates GitHub account `anuragrathod`, but full student name, roll number, college, and department are uncommitted. | Candidate fills in official institutional registration details. | Title Page, Certificate, Declaration, Acknowledgement | **CRITICAL** (Must be completed before printing) |
| **MIC-02** | **Project Guide & Supervisor Details** | Academic thesis standards require the Guide's name, academic title, and departmental affiliation. | **Absent from repository.** | Project author contacts assigned project supervisor or faculty advisor. | Certificate Page, Acknowledgements | **CRITICAL** |
| **MIC-03** | **Production NVIDIA NIM API Tier & Rate Limits** | Accurate cost-benefit analysis in Chapter 7 and Chapter 8 requires accounting for Free-Tier limits (40 RPM across the account) and paid NIM deployment scaling. | **Fully Configured.** Code supports 3 keys from the same account and strictly enforces shared 40 RPM rate limiting with backoff. | Check API quota limits in the NVIDIA Build portal ([build.nvidia.com](https://build.nvidia.com/)). | Chapter 3 (Cost Constraints), Chapter 7 (Performance Discussion) | **HIGH** |
| **MIC-04** | **Real-World Recruiter Trial Metrics** | Academic reports require user testing feedback (e.g., System Usability Scale, time-to-screen metrics, human audit error rates). | **Excluded by Design.** Repository strictly excludes real candidate resumes in `.gitignore` to prevent PII leakage; tests utilize synthetic data (`eval_data/dataset.py`). | Conduct a pilot test with 5–10 real recruiters using anonymized production resumes and log elapsed time and accuracy scores. | Chapter 6 (Testing & Validation), Chapter 7 (Results & Discussion) | **HIGH** |
| **MIC-05** | **Benchmark Hardware Specifications** | Test environment hardware must be explicitly recorded (CPU clock speed, core count, RAM, SSD I/O rate) for reproducibility of the >900 resumes/sec benchmark. | **Not Logged.** `PROJECT_AUDIT.md` notes Linux x86_64, but exact CPU architecture (e.g., Intel Core i7-12700H vs AMD Ryzen 7 5800X) is not saved. | Run `lscpu` or `wmic cpu get name` on the benchmarking machine and record physical hardware specs. | Chapter 6 (Testing Environment), Chapter 7 (Benchmark Analysis) | **MEDIUM** |
| **MIC-06** | **Institutional Thesis Formatting Guidelines** | Universities mandate specific margins (e.g. 1.25" left margin for binding), font sizes (Times New Roman 12pt / 1.5 line spacing), and citation formats (IEEE vs APA). | **Generic Standard Provided.** Dossier provides IEEE format. | Review the official Department Project Report Manual or thesis template guidelines. | Preliminary Pages, Bibliography, Entire Document Layout | **MEDIUM** |
| **MIC-07** | **Physical Desktop Screenshots (Headed OS)** | Visual evidence of the Tkinter desktop GUI running natively on Windows 11 and Ubuntu with real resumes. | **Code Ready, Screenshots Not Committed.** `gui.py` is fully implemented, but binary PNG screenshots are omitted to maintain repository cleanliness. | Launch `python gui.py`, load sample resumes, trigger extraction, and take high-resolution PNG window captures. | Chapter 7 (Visual Results), Appendix (User Guide) | **MEDIUM** |

---

## 2. Verification Procedure for Missing Items

```
┌─────────────────────────────────────────────────────────────┐
│             Pre-Report Verification Workflow                │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
     [Academic Metadata]              [Empirical Verification]
     1. Author Full Name              1. Launch gui.py on target OS
     2. Student Roll / ID             2. Capture High-Res Screenshots
     3. Department & College          3. Record Hardware Specs (CPU/RAM)
     4. Supervisor Signature          4. Run benchmark.py on 100+ files
               │                               │
               └───────────────┬───────────────┘
                               ▼
               [Compile Final Bound Thesis]
```
