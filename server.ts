import express, { Request, Response } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';
import { GoogleGenAI } from '@google/genai';

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 3000;
const isProduction = process.env.NODE_ENV === 'production';

app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Read prompt template
let promptTemplate = '';
const promptPath = path.join(__dirname, 'prompts', 'extract_candidate.txt');
if (fs.existsSync(promptPath)) {
  promptTemplate = fs.readFileSync(promptPath, 'utf-8');
} else {
  promptTemplate = `You are an expert talent intelligence resume extraction assistant.
Extract all candidate information from the resume text into the required JSON schema with 100% precision.
Schema:
{
  "full_name": null,
  "email": null,
  "phone": null,
  "location": null,
  "linkedin_url": null,
  "github_url": null,
  "portfolio_url": null,
  "education": [{"qualification": null, "specialization": null, "institution": null, "start_year": null, "graduation_year": null}],
  "work_experience": [{"employer": null, "job_title": null, "start_date": null, "end_date": null, "summary": null, "responsibilities": [], "description": null}],
  "projects": [{"name": null, "summary": null, "description": null, "technologies": []}],
  "technical_skills": [],
  "programming_languages": [],
  "tools": [],
  "certifications": []
}
<RESUME_TEXT>
{resume_text}
</RESUME_TEXT>
Return ONLY a valid JSON object matching the schema.`;
}

// -------------------------------------------------------------
// API Routes
// -------------------------------------------------------------

app.get('/api/status', (req: Request, res: Response) => {
  const geminiKey = process.env.GEMINI_API_KEY || '';
  const groqKey = process.env.GROQ_API_KEY || '';

  res.json({
    gemini_available: Boolean(geminiKey),
    groq_available: Boolean(groqKey),
    active_engine: geminiKey ? 'gemini' : groqKey ? 'groq' : 'rules_only',
    models: [
      { id: 'gemini-3.8-flash', name: 'Gemini 3.8 Flash (Recommended - Fast & Accurate)', provider: 'gemini' },
      { id: 'gemini-3.1-flash-lite', name: 'Gemini 3.1 Flash Lite (High-Speed)', provider: 'gemini' },
      { id: 'openai/gpt-oss-120b', name: 'Groq: GPT-OSS 120B', provider: 'groq' },
      { id: 'openai/gpt-oss-20b', name: 'Groq: GPT-OSS 20B', provider: 'groq' },
      { id: 'qwen/qwen3.8-27b', name: 'Groq: Qwen 3.8 27B', provider: 'groq' },
      { id: 'rules_only', name: 'Rules-Only Mode (Offline / Regex)', provider: 'rules_only' },
    ],
  });
});

app.post('/api/extract', async (req: Request, res: Response) => {
  const { text, filename, provider = 'auto', model = 'gemini-3.8-flash', customApiKey } = req.body;

  if (!text || typeof text !== 'string' || !text.trim()) {
    res.status(400).json({ success: false, error: 'Empty resume text.' });
    return;
  }

  // Build prompt
  const prompt = promptTemplate.replace('{resume_text}', text.slice(0, 30000));

  // Determine provider
  const effectiveGeminiKey = process.env.GEMINI_API_KEY || (provider === 'gemini' ? customApiKey : '');
  const effectiveGroqKey = customApiKey || process.env.GROQ_API_KEY || '';

  let effectiveProvider = provider;
  if (provider === 'auto') {
    if (effectiveGeminiKey) effectiveProvider = 'gemini';
    else if (effectiveGroqKey) effectiveProvider = 'groq';
    else effectiveProvider = 'rules_only';
  }

  if (effectiveProvider === 'rules_only') {
    res.json({
      success: false,
      is_rules_only: true,
      message: 'Rules-only mode active. Extraction handled by client regex engine.',
    });
    return;
  }

  // Provider: Gemini
  if (effectiveProvider === 'gemini') {
    const candidateModels = [
      model && model.startsWith('gemini') ? model : 'gemini-3.8-flash',
      'gemini-3.1-flash-lite',
      'gemini-flash-latest',
    ];

    let lastError: any = null;
    const apiKey = effectiveGeminiKey || process.env.GEMINI_API_KEY;
    const ai = new GoogleGenAI(apiKey ? { apiKey } : undefined);

    for (const targetModel of candidateModels) {
      try {
        const response = await ai.models.generateContent({
          model: targetModel,
          contents: prompt,
          config: {
            responseMimeType: 'application/json',
            temperature: 0,
          },
        });

        const responseText = response.text || '';
        let parsed = JSON.parse(responseText);

        res.json({
          success: true,
          data: parsed,
          provider: 'gemini',
          model_used: targetModel,
        });
        return;
      } catch (err: any) {
        lastError = err;
        console.warn(`[${filename}] Gemini ${targetModel} attempt failed:`, err?.message || err);
      }
    }

    // If all Gemini attempts fail, try Groq if key is present
    if (effectiveGroqKey) {
      effectiveProvider = 'groq';
    } else {
      res.json({
        success: false,
        error: `AI extraction unavailable (${lastError?.message || 'High demand'}). Using rule-based extraction.`,
        fallback_to_rules: true,
      });
      return;
    }
  }

  // Provider: Groq
  if (effectiveProvider === 'groq') {
    try {
      const groqKey = effectiveGroqKey;
      if (!groqKey) {
        res.json({
          success: false,
          error: 'No Groq API key configured. Using rule-based extraction.',
          fallback_to_rules: true,
        });
        return;
      }

      const groqModel = model.startsWith('gemini') ? 'openai/gpt-oss-120b' : model;
      const groqResp = await fetch('https://api.groq.com/openai/v1/chat/completions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${groqKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: groqModel,
          messages: [
            {
              role: 'system',
              content:
                'You are a meticulous talent intelligence extraction AI. Output strictly valid JSON matching the schema.',
            },
            { role: 'user', content: prompt },
          ],
          response_format: { type: 'json_object' },
          temperature: 0,
          max_completion_tokens: 4096,
        }),
      });

      if (!groqResp.ok) {
        const errText = await groqResp.text();
        throw new Error(`Groq HTTP ${groqResp.status}: ${errText}`);
      }

      const groqData = await groqResp.json();
      const rawContent = groqData.choices?.[0]?.message?.content || '{}';
      const parsed = JSON.parse(rawContent);

      res.json({
        success: true,
        data: parsed,
        provider: 'groq',
        model_used: groqModel,
      });
      return;
    } catch (err: any) {
      console.warn(`[${filename}] Groq extraction failed:`, err?.message || err);
      res.json({
        success: false,
        error: `Groq extraction failed: ${err?.message || err}`,
        fallback_to_rules: true,
      });
      return;
    }
  }

  res.json({ success: false, fallback_to_rules: true });
});

// -------------------------------------------------------------
// Dev & Production Server Mounting
// -------------------------------------------------------------

async function startServer() {
  if (!isProduction) {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true, host: '0.0.0.0', port: PORT },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(__dirname, 'dist');
    if (fs.existsSync(distPath)) {
      app.use(express.static(distPath));
      app.get('*', (req, res) => {
        res.sendFile(path.join(distPath, 'index.html'));
      });
    }
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`ResumeDrop server running on http://0.0.0.0:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error('Failed to start server:', err);
});
