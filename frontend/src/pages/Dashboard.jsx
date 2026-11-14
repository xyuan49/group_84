
import { useEffect, useState } from 'react';
import {
    getPatients,
    getGlucose,
    getA1c,
    getInsulin,
} from '../services/api';

import GlucoseChart from '../components/GlucoseChart';
import HbA1cChart from '../components/HbA1cChart';
import InsulinChart from '../components/InsulinChart';
import ManualLogging from '../components/ManualLogging';
import MessagingPortal from '../components/MessagingPortal';

export default function Dashboard() {
    const [patients, setPatients] = useState([]);
    const [selectedId, setSelectedId] = useState('');

    // Chart data
    const [readings, setReadings] = useState([]);
    const [a1cReadings, setA1cReadings] = useState([]);
    const [insulinReadings, setInsulinReadings] = useState([]);

    // Loading states
    const [loadingPatients, setLoadingPatients] = useState(true);
    const [loadingGlucose, setLoadingGlucose] = useState(false);
    const [loadingA1c, setLoadingA1c] = useState(false);
    const [loadingInsulin, setLoadingInsulin] = useState(false);

    const [error, setError] = useState('');

    // Load patient list
    useEffect(() => {
        let active = true;

        getPatients()
            .then((data) => {
                if (!active) return;

                setPatients(data);

                if (data.length > 0) {
                    setSelectedId(data[0].id);
                }
            })
            .catch((err) => {
                if (active) setError(err.message);
            })
            .finally(() => {
                if (active) setLoadingPatients(false);
            });

        return () => {
            active = false;
        };
    }, []);

    // Load chart data whenever the selected patient changes
    useEffect(() => {
        if (!selectedId) return;

        let active = true;

        setReadings([]);
        setA1cReadings([]);
        setInsulinReadings([]);

        setLoadingGlucose(true);
        setLoadingA1c(true);
        setLoadingInsulin(true);
        setError('');

        getGlucose(selectedId)
            .then((data) => {
                if (active) setReadings(data);
            })
            .catch((err) => {
                if (active) setError(err.message);
            })
            .finally(() => {
                if (active) setLoadingGlucose(false);
            });

        getA1c(selectedId)
            .then((data) => {
                if (active) setA1cReadings(data);
            })
            .catch((err) => {
                if (active) setError(err.message);
            })
            .finally(() => {
                if (active) setLoadingA1c(false);
            });

        getInsulin(selectedId)
            .then((data) => {
                if (active) setInsulinReadings(data);
            })
            .catch((err) => {
                if (active) setError(err.message);
            })
            .finally(() => {
                if (active) setLoadingInsulin(false);
            });

        return () => {
            active = false;
        };
    }, [selectedId]);

    function handlePatientChange(event) {
        setSelectedId(event.target.value);
    }

    return (
        <main className="dashboard">
            {/* Header */}
            <header className="dashboard-header">
                <h1>GlucoTrack</h1>
                <p>Diabetes Management Dashboard</p>
            </header>

            {/* Patient selection */}
            <div className="patient-selector">
                <label htmlFor="patient">Select Patient</label>

                <select
                    id="patient"
                    value={selectedId}
                    onChange={handlePatientChange}
                    disabled={loadingPatients}
                >
                    {patients.map((patient) => (
                        <option key={patient.id} value={patient.id}>
                            {patient.first_name} {patient.last_name}
                        </option>
                    ))}
                </select>
            </div>

            {error && (
                <p role="alert" className="error">
                    {error}
                </p>
            )}

            {loadingPatients && <p>Loading patients...</p>}

            {/* Glucose chart */}
            {loadingGlucose ? (
                <p>Loading glucose history...</p>
            ) : selectedId ? (
                <GlucoseChart readings={readings} />
            ) : null}

            {/* HbA1c chart */}
            {loadingA1c ? (
                <p>Loading HbA1c history...</p>
            ) : selectedId ? (
                <HbA1cChart readings={a1cReadings} />
            ) : null}

            {/* Insulin chart */}
            {loadingInsulin ? (
                <p>Loading insulin history...</p>
            ) : selectedId ? (
                <InsulinChart readings={insulinReadings} />
            ) : null}

            {/* Manual logging */}
            {selectedId && (
                <ManualLogging
                    key={selectedId}
                    patientId={selectedId}
                />
            )}

            {/* Patient-provider messaging */}
            {selectedId && (
                <MessagingPortal
                    key={`messages-${selectedId}`}
                    patientId={selectedId}
                />
            )}
        </main>
    );
}
