
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ReferenceLine,
} from 'recharts';
import { sourceLabel } from '../dataSources';

export default function HbA1cChart({ readings = [] }) {
    const data = readings
        .filter((item) =>
            item.value != null &&
            Number.isFinite(Number(item.value)) &&
            item.effective_at
        )
        .map((item) => ({
            date: new Date(item.effective_at).getTime(),
            value: Number(item.value),
        }))
        .filter((item) => Number.isFinite(item.date))
        .sort((a, b) => a.date - b.date);

    return (
        <section className="chart-card">
            <h2>HbA1c History</h2>
            <p>Hemoglobin A1c measurements over time</p>
            <p className="source-note">Source: {sourceLabel('fhir')}</p>

            {data.length === 0 ? (
                <p>No HbA1c measurements available for this patient.</p>
            ) : (
                <div style={{ width: '100%', height: 300 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                            data={data}
                            margin={{ top: 20, right: 30, left: 10, bottom: 10 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" />

                            <XAxis
                                dataKey="date"
                                type="number"
                                scale="time"
                                domain={['dataMin', 'dataMax']}
                                tickFormatter={(timestamp) =>
                                    new Date(timestamp).getFullYear()
                                }
                            />

                            <YAxis
                                domain={[0, 'auto']}
                                tickFormatter={(value) => `${value}%`}
                            />

                            <Tooltip
                                labelFormatter={(timestamp) =>
                                    new Date(timestamp).toLocaleDateString()
                                }
                                formatter={(value) => [
                                    `${Number(value).toFixed(2)}%`,
                                    'HbA1c',
                                ]}
                            />

                            <ReferenceLine
                                y={7}
                                stroke="#e59b36"
                                strokeDasharray="5 5"
                                label="7%"
                            />

                            <Line
                                type="monotone"
                                dataKey="value"
                                stroke="#0d9488"
                                strokeWidth={2.5}
                                dot={{ r: 3 }}
                                activeDot={{ r: 6 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            )}
        </section>
    );
}
