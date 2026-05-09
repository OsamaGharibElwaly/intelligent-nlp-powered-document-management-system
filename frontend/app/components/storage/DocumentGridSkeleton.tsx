"use client";

import styles from "./documentStorage.module.css";

type Props = {
  count?: number;
};

export function DocumentGridSkeleton({ count = 8 }: Props) {
  return (
    <div data-testid="documents-grid-skeleton" className={styles.grid} aria-busy="true" aria-label="Loading documents">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={styles.skeletonCard} />
      ))}
    </div>
  );
}
