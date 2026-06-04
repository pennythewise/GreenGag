import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';

/**
 * Cross-card linkage state. Clicking a discrepancy, a flagged ledger row, or a
 * PDF claim sets the active claim id so every card can co-highlight the same
 * triangulated evidence (the heart of the XAI lineage interface).
 */
interface SelectionState {
  activeClaimId: string | null;
  activeDiscrepancyId: string | null;
  setActiveClaim: (id: string | null) => void;
  setActiveDiscrepancy: (id: string | null) => void;
}

const SelectionContext = createContext<SelectionState | null>(null);

export function SelectionProvider({ children }: { children: ReactNode }) {
  const [activeClaimId, setActiveClaimId] = useState<string | null>(null);
  const [activeDiscrepancyId, setActiveDiscrepancyId] = useState<string | null>(null);

  const value = useMemo<SelectionState>(
    () => ({
      activeClaimId,
      activeDiscrepancyId,
      setActiveClaim: setActiveClaimId,
      setActiveDiscrepancy: setActiveDiscrepancyId,
    }),
    [activeClaimId, activeDiscrepancyId],
  );

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export function useSelection(): SelectionState {
  const ctx = useContext(SelectionContext);
  if (!ctx) throw new Error('useSelection must be used within SelectionProvider');
  return ctx;
}
