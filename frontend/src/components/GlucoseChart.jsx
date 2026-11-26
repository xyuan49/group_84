
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceArea,
    ReferenceLine,
} from 'recharts';
import SourceNote from './SourceNote';
import { sourceLabel } from '../dataSources';

export default function GlucoseChart({ readings }) {
    if (!readings.length) {
        return <p>No glucose readings available for this patient.</p>;
    }

    // CGM datasets can contain more than 1,000 readings.
    // Group readings into hourly averages for a readable chart.
    const hourly = new Map();

    readings.forEach((reading) => {
        const hour = reading.measured_at.slice(0, 13);
        const entry = hourly.get(hour) || { total: 0, count: 0, sources: new Set() };

        entry.total += reading.value_mg_dl;
        entry.count += 1;
        entry.sources.add(reading.source);
        hourly.set(hour, entry);
    });

    const data = Array.from(hourly, ([hour, entry]) => ({
        timestamp: hour,
        glucose: Math.round(entry.total / entry.count),
        sources: Array.from(entry.sources).map(sourceLabel).join(', '),
    })).sort((a, b) => a.timestamp.localeCompare(b.timestamp));

    return (
        <section className="chart-card">
            <h2>Glucose History</h2>
            <p>Last 14 days of available readings</p>
            <SourceNote records={readings} />

            <ResponsiveContainer width="100%" height={300}>
                <LineChart data={data}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                        dataKey="timestamp"
                        tickFormatter={(value) => value.slice(5, 10)}
                        minTickGap={35}
                    />
                    <YAxis unit=" mg/dL" width={85} />
                    <Tooltip
                        labelFormatter={(value, payload) => {
                            const time = value.replace('T', ' ') + ':00';
                            const sources = payload?.[0]?.payload?.sources;
                            return sources ? `${time} · ${sources}` : time;
                        }}
                        formatter={(value) => [`${value} mg/dL`, 'Glucose']}
                    />
                    <ReferenceArea y1={70} y2={180} fill="#16a34a" fillOpacity={0.1} />
                    <ReferenceLine y={70} stroke="#16a34a" strokeDasharray="4 4" />
                    <ReferenceLine y={180} stroke="#16a34a" strokeDasharray="4 4" />
                    <Line
                        type="monotone"
                        dataKey="glucose"
                        stroke="#0d9488"
                        strokeWidth={2}
                        dot={false}
                        connectNulls={false}
                    />
                </LineChart>
            </ResponsiveContainer>
        </section>
    );
}
