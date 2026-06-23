import type { ExtractedClaim, ReportParserState } from '../types/audit';

export interface IngestResponse {
  document_id: string;
  original_filename: string;
  ingest_status: string;
  chunk_count: number;
  deduplicated?: boolean;
  mode: 'mock' | 'live';
}

export interface ExtractResponse {
  document_id: string;
  extract_status: string;
  claim_count: number;
  claims: ExtractedClaim[];
  report_parser: ReportParserState;
  pillar_status: Record<string, unknown>;
  extraction_notes: string[];
  mode: 'mock' | 'live';
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function ingestDocument(file: File): Promise<IngestResponse> {
  const form = new FormData();
  form.append('file', file);
  const res = await fetch('/api/documents/ingest', { method: 'POST', body: form });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

export async function extractClaims(documentId: string): Promise<ExtractResponse> {
  const res = await fetch(`/api/documents/${documentId}/extract`, { method: 'POST' });
  if (!res.ok) throw new Error(await parseError(res));
  return res.json();
}

/** Sample shortcut — backend returns deterministic mock fixture data. */
export async function ingestSampleReport(): Promise<IngestResponse> {
  return {
    document_id: 'mock-document',
    original_filename: '2025_Sustainability_Net-Zero_Pathway.pdf',
    ingest_status: 'ready',
    chunk_count: 24,
    mode: 'mock',
  };
}
