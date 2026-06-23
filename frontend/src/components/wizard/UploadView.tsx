import { useRef, useState } from 'react';
import { UploadCloud, FileText, Sparkles, ArrowRight, Loader2 } from 'lucide-react';
import type { AuditMeta } from '../../types/audit';
import './wizard.css';

interface Props {
  meta: AuditMeta;
  onIngest: (input: { file?: File; sample?: boolean }) => Promise<void>;
  busy?: boolean;
  error?: string | null;
}

/**
 * Step 1 — Upload. A real drag-and-drop PDF dropzone plus a "use sample report"
 * shortcut. Since there is no backend, either action triggers the same canned
 * Malaya BuildCorp audit flow.
 */
export function UploadView({ meta, onIngest, busy = false, error }: Props) {
  const [dragging, setDragging] = useState(false);
  const [picked, setPicked] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function accept(file: File | undefined) {
    if (!file) return;
    setPicked(file);
  }

  return (
    <div className="wz gg-fade-in">
      <header className="wz__head">
        <span className="wz__eyebrow">Step 1 · Input Layer</span>
        <h1 className="wz__title">Upload an ESG or sustainability report</h1>
        <p className="wz__lede">
          GreenGag extracts specific environmental claims and cross-verifies each one against
          independent financial, media, NGO, and geospatial evidence — producing an explainable
          greenwashing-risk score for human review.
        </p>
      </header>

      <div
        className={`wz-drop ${dragging ? 'is-dragging' : ''} ${picked ? 'is-picked' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          accept(e.dataTransfer.files?.[0]);
        }}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          hidden
          onChange={(e) => accept(e.target.files?.[0] ?? undefined)}
        />
        {picked ? (
          <div className="wz-drop__file">
            <FileText size={26} className="wz-drop__file-icon" />
            <div>
              <div className="wz-drop__file-name">{picked.name}</div>
              <div className="wz-drop__file-meta">
                {(picked.size / 1024 / 1024).toFixed(2)} MB · ready to analyse
              </div>
            </div>
          </div>
        ) : (
          <>
            <div className="wz-drop__icon">
              <UploadCloud size={30} />
            </div>
            <div className="wz-drop__primary">Drag &amp; drop a PDF here</div>
            <div className="wz-drop__secondary">or click to browse — public reports only</div>
          </>
        )}
      </div>

      <div className="wz-upload__actions">
        <button
          className="wz-btn wz-btn--ghost"
          disabled={busy}
          onClick={() => void onIngest({ sample: true })}
        >
          <Sparkles size={16} />
          Use sample report
        </button>
        <button
          className="wz-btn wz-btn--primary"
          disabled={!picked || busy}
          onClick={() => picked && void onIngest({ file: picked })}
        >
          {busy ? <Loader2 size={16} className="wz-spin" /> : null}
          Extract claims
          <ArrowRight size={16} />
        </button>
      </div>

      {error && <div className="wz-error">{error}</div>}

      <div className="wz-sample">
        <div className="wz-sample__tag">Sample case loaded for this demo</div>
        <div className="wz-sample__entity">{meta.target_entity}</div>
        <div className="wz-sample__project">{meta.project_name}</div>
        <p className="wz-sample__note">
          Demonstration uses a fictional entity and simulated evidence. Outputs are
          decision-support risk indicators, not legal accusations.
        </p>
      </div>
    </div>
  );
}
