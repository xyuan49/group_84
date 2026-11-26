
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function getData(path) {
    const response = await fetch(`${API_BASE}${path}`);

    if (!response.ok) {
        throw new Error(`API request failed (${response.status})`);
    }

    return response.json();
}

export function getPatients() {
    return getData('/api/patients?limit=100');
}

export function getGlucose(patientId) {
    return getData(
        `/api/patients/${encodeURIComponent(patientId)}/glucose?days=14`
    );
}

export function getA1c(patientId) {
    return getData(
        `/api/patients/${encodeURIComponent(patientId)}/observations?code=4548-4`
    );
}

export function getInsulin(patientId) {
    return getData(
        `/api/patients/${encodeURIComponent(patientId)}/insulin?days=14`
    );
}

async function postData(path, body, what) {
    const response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });

    if (!response.ok) {
        throw new Error(`Could not save ${what} (${response.status})`);
    }

    return response.json();
}

export function createGlucose(patientId, body) {
    return postData(
        `/api/patients/${encodeURIComponent(patientId)}/glucose`,
        body,
        'glucose reading'
    );
}

export function createInsulin(patientId, body) {
    return postData(
        `/api/patients/${encodeURIComponent(patientId)}/insulin`,
        body,
        'insulin dose'
    );
}

export function createMeal(patientId, body) {
    return postData(
        `/api/patients/${encodeURIComponent(patientId)}/meals`,
        body,
        'meal'
    );
}
