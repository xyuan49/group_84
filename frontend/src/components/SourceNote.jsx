import { countBySource, sourceLabel } from '../dataSources';

// "Sources: Shanghai T2DM CGM dataset (paired for demonstration), 1,296 readings · Patient entries, 2 readings"
export default function SourceNote({ records, noun = 'readings' }) {
    const counts = countBySource(records);
    if (!counts.length) return null;

    return (
        <p className="source-note">
            Sources:{' '}
            {counts
                .map(({ source, count }) => {
                    const word = count === 1 ? noun.replace(/s$/, '') : noun;
                    return `${sourceLabel(source)}, ${count.toLocaleString('en-US')} ${word}`;
                })
                .join(' · ')}
        </p>
    );
}
