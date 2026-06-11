import { useRef, useState } from 'react';
import { UploadCloud, FileText, Sparkles, ArrowRight } from 'lucide-react';
import type { AuditMeta } from '../../types/audit';
import './wizard.css';

interface Props {
  meta: AuditMeta;
  onIngest: (fileName: string) => void;
}

/**
 * Step 1 — Upload. A real drag-and-drop PDF dropzone plus a "use sample report"
 * shortcut. Since there is no backend, either action triggers the same canned
 * Malaya BuildCorp audit flow.
 */
export function UploadView({ meta, onIngest }: Props) {
  const [dragging, setDragging] = useState(false);
  const [picked, setPicked] = useState<{ name: string; size: string } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function accept(file: File | undefined) {
    if (!file) return;
    setPicked({ name: file.name, size: `${(file.size / 1024 / 1024).toFixed(2)} MB` });
  }

  const sampleName = '2025_Sustainability_Net-Zero_Pathway.pdf';

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
              <div className="wz-drop__file-meta">{picked.size} · ready to analyse</div>
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
          onClick={() => onIngest(sampleName)}
        >
          <Sparkles size={16} />
          Use sample report
        </button>
        <button
          className="wz-btn wz-btn--primary"
          disabled={!picked}
          onClick={() => picked && onIngest(picked.name)}
        >
          Extract claims
          <ArrowRight size={16} />
        </button>
      </div>

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
