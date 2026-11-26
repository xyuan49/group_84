import { useEffect, useState } from 'react';
import { getAlerts } from '../services/api';

const SEVERITY_LABELS = { urgent: 'Urgent', warning: 'Check', info: 'Info' };

// Rule-based alerts from /api/patients/{id}/alerts, most severe first.
// `refreshKey` changes when new data is saved, so the alerts reload.
export default function AlertsPanel({ patientId, refreshKey = 0, days = 7 }) {
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');

    useEffect(() => {
        let active = true;

        getAlerts(patientId, days)
            .then((data) => {
                if (!active) return;
                setResult(data);
                setError('');
            })
            .catch((err) => {
                if (active) setError(err.message);
            });

        return () => {
            active = false;
        };
    }, [patientId, refreshKey, days]);

    const alerts = result?.alerts ?? [];
    const emergency = alerts.find((alert) => alert.emergency);
    const others = alerts.filter((alert) => alert !== emergency);

    return (
        <section className="chart-card alerts-panel">
            <h2>Alerts</h2>
            <p>Rule-based checks of the last {days} days of glucose and the latest labs</p>

            {error && <p role="alert" className="error">Could not load alerts: {error}</p>}

            {!result && !error && <p>Loading alerts...</p>}

            {emergency && (
                <div className="emergency-alert" role="alert">
                    <strong>{emergency.title}</strong>
                    <span>{emergency.detail}</span>
                    <button type="button" disabled title="Simulated: this demo contacts no one">
                        Call emergency services (simulated)
                    </button>
                </div>
            )}

            {result && alerts.length === 0 && (
                <p>No alerts: readings and latest labs are within goals.</p>
            )}

            {others.length > 0 && (
                <ul className="alert-list">
                    {others.map((alert) => (
                        <li key={alert.rule} className={`alert-item alert-${alert.severity}`}>
                            <span className="alert-severity">{SEVERITY_LABELS[alert.severity]}</span>
                            <div>
                                <strong>{alert.title}</strong>
                                <span className="alert-detail">{alert.detail}</span>
                            </div>
                        </li>
                    ))}
                </ul>
            )}

            <p className="source-note">
                Thresholds follow ADA Standards of Care. GlucoTrack is a student project, not medical advice.
            </p>
        </section>
    );
}
