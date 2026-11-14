
import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
} from 'recharts';

export default function InsulinChart({ readings = [] }) {
    // Group insulin doses by day and insulin type
    const dailyTotals = {};

    readings.forEach((reading) => {
        if (!reading.administered_at) return;

        const units = Number(reading.units);
        if (!Number.isFinite(units) || units < 0) return;

        const date = reading.administered_at.slice(0, 10);

        if (!dailyTotals[date]) {
            dailyTotals[date] = {
                date,
                short: 0,
                intermediate: 0,
                long: 0,
                other: 0,
            };
        }

        const type = String(reading.insulin_type || '').toLowerCase();

        if (['short', 'intermediate', 'long'].includes(type)) {
            dailyTotals[date][type] += units;
        } else {
            dailyTotals[date].other += units;
        }
    });

    const data = Object.values(dailyTotals)
        .sort((a, b) => a.date.localeCompare(b.date));

    const formatDate = (date) => {
        const [, month, day] = date.split('-');
        return `${month}/${day}`;
    };

    return (
        <section className="chart-card">
            <h2>Insulin History</h2>
            <p>Daily insulin doses by type (last 14 days)</p>

            {data.length === 0 ? (
                <p>No insulin records available for this patient.</p>
            ) : (
                <div style={{ width: '100%', height: 320 }}>
                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                            data={data}
                            margin={{
                                top: 20,
                                right: 30,
                                left: 10,
                                bottom: 10,
                            }}
                        >
                            <CartesianGrid
                                strokeDasharray="3 3"
                                vertical={false}
                            />

                            <XAxis
                                dataKey="date"
                                tickFormatter={formatDate}
                            />

                            <YAxis
                                label={{
                                    value: 'Units',
                                    angle: -90,
                                    position: 'insideLeft',
                                }}
                            />

                            <Tooltip
                                labelFormatter={(date) => date}
                                formatter={(value, name) => [
                                    `${Number(value).toFixed(1)} units`,
                                    name,
                                ]}
                            />

                            <Legend />

                            <Bar
                                dataKey="short"
                                name="Short-acting"
                                stackId="insulin"
                                fill="#0d9488"
                            />

                            <Bar
                                dataKey="intermediate"
                                name="Intermediate-acting"
                                stackId="insulin"
                                fill="#f59e0b"
                            />

                            <Bar
                                dataKey="long"
                                name="Long-acting"
                                stackId="insulin"
                                fill="#6366f1"
                            />

                            <Bar
                                dataKey="other"
                                name="Other"
                                stackId="insulin"
                                fill="#94a3b8"
                            />
                        </BarChart>
                    </ResponsiveContainer>
                </div>
            )}
        </section>
    );
}
