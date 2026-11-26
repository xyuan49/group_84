// Where each glucose, insulin or meal record came from (the API's `source` field).
// UCI and Shanghai records come from research datasets about other people and
// were paired with synthetic Synthea patients for demonstration.
export const DATA_SOURCES = {
    fhir: { label: 'Synthetic health record (Synthea, FHIR)', paired: false },
    user: { label: 'Patient entries', paired: false },
    uci: { label: 'UCI Diabetes dataset', paired: true },
    cgm: { label: 'Shanghai T2DM CGM dataset', paired: true },
};

export function sourceLabel(source) {
    const known = DATA_SOURCES[source];
    if (!known) return source || 'Unknown source';
    return known.paired ? `${known.label} (paired for demonstration)` : known.label;
}

// [{ source, count }] in order of first appearance.
export function countBySource(records) {
    const counts = new Map();
    records.forEach((record) => {
        counts.set(record.source, (counts.get(record.source) || 0) + 1);
    });
    return Array.from(counts, ([source, count]) => ({ source, count }));
}
