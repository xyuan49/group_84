
import { useState } from 'react';
import { createGlucose, createInsulin, createMeal } from '../services/api';

const initialGlucose = {
    value: '',
    measuredAt: '',
    mealContext: 'fasting',
};

const initialInsulin = {
    units: '',
    insulinType: 'rapid',
    administeredAt: '',
};

const initialNutrition = {
    description: '',
    carbs: '',
    calories: '',
    eatenAt: '',
};

// Empty optional number fields are sent as null, not 0.
function optionalNumber(value) {
    return value === '' ? null : Number(value);
}

export default function ManualLogging({ patientId, onGlucoseSaved, onInsulinSaved, onMealSaved }) {
    const [activeTab, setActiveTab] = useState('glucose');

    const [glucose, setGlucose] = useState(initialGlucose);
    const [insulin, setInsulin] = useState(initialInsulin);
    const [nutrition, setNutrition] = useState(initialNutrition);

    // One save in flight at a time; messages belong to the open form.
    const [saving, setSaving] = useState(false);
    const [saveError, setSaveError] = useState('');
    const [saveStatus, setSaveStatus] = useState('');

    function switchTab(tab) {
        setActiveTab(tab);
        setSaveError('');
        setSaveStatus('');
    }

    async function save(event, request, onSuccess, message) {
        event.preventDefault();

        if (!patientId || saving) return;

        setSaving(true);
        setSaveError('');
        setSaveStatus('');

        try {
            await request();
        } catch (error) {
            setSaveError(error.message);
            setSaving(false);
            return;
        }

        setSaving(false);
        setSaveStatus(message);
        onSuccess();
    }

    function handleGlucoseSubmit(event) {
        return save(
            event,
            () => createGlucose(patientId, {
                value_mg_dl: Number(glucose.value),
                measured_at: glucose.measuredAt,
                meal_context: glucose.mealContext || null,
            }),
            () => {
                setGlucose(initialGlucose);
                onGlucoseSaved?.();
            },
            'Glucose reading saved.'
        );
    }

    function handleInsulinSubmit(event) {
        return save(
            event,
            () => createInsulin(patientId, {
                units: Number(insulin.units),
                insulin_type: insulin.insulinType || null,
                administered_at: insulin.administeredAt,
            }),
            () => {
                setInsulin(initialInsulin);
                onInsulinSaved?.();
            },
            'Insulin dose saved.'
        );
    }

    function handleNutritionSubmit(event) {
        return save(
            event,
            () => createMeal(patientId, {
                description: nutrition.description.trim(),
                carbs_g: optionalNumber(nutrition.carbs),
                calories: optionalNumber(nutrition.calories),
                eaten_at: nutrition.eatenAt,
            }),
            () => {
                setNutrition(initialNutrition);
                onMealSaved?.();
            },
            'Meal saved.'
        );
    }

    const handleGlucoseChange = (event) => {
        const { name, value } = event.target;

        setGlucose((previous) => ({
            ...previous,
            [name]: value,
        }));
    };

    const handleInsulinChange = (event) => {
        const { name, value } = event.target;

        setInsulin((previous) => ({
            ...previous,
            [name]: value,
        }));
    };

    const handleNutritionChange = (event) => {
        const { name, value } = event.target;

        setNutrition((previous) => ({
            ...previous,
            [name]: value,
        }));
    };

    const messages = (
        <>
            {saveError && <p role="alert">{saveError}</p>}
            <p role="status">{saveStatus}</p>
        </>
    );

    return (
        <section className="chart-card">
            <h2>Manual Logging</h2>
            <p>
                Record glucose readings, insulin doses, and meals.
            </p>

            <div
                className="logging-tabs"
                style={{
                    display: 'flex',
                    gap: '10px',
                    marginBottom: '20px',
                    flexWrap: 'wrap',
                }}
            >
                <button
                    type="button"
                    onClick={() => switchTab('glucose')}
                    aria-pressed={activeTab === 'glucose'}
                >
                    Glucose
                </button>

                <button
                    type="button"
                    onClick={() => switchTab('insulin')}
                    aria-pressed={activeTab === 'insulin'}
                >
                    Insulin
                </button>

                <button
                    type="button"
                    onClick={() => switchTab('nutrition')}
                    aria-pressed={activeTab === 'nutrition'}
                >
                    Nutrition
                </button>
            </div>

            {activeTab === 'glucose' && (
                <form onSubmit={handleGlucoseSubmit}>
                    <h3>Log Glucose Reading</h3>

                    <div className="form-field">
                        <label htmlFor="glucose-value">
                            Blood Glucose (mg/dL)
                        </label>
                        <input
                            id="glucose-value"
                            name="value"
                            type="number"
                            min="20"
                            max="600"
                            step="any"
                            required
                            value={glucose.value}
                            onChange={handleGlucoseChange}
                            placeholder="e.g. 120"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="glucose-time">
                            Date and Time
                        </label>
                        <input
                            id="glucose-time"
                            name="measuredAt"
                            type="datetime-local"
                            required
                            value={glucose.measuredAt}
                            onChange={handleGlucoseChange}
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="meal-context">
                            Meal Context
                        </label>
                        <select
                            id="meal-context"
                            name="mealContext"
                            value={glucose.mealContext}
                            onChange={handleGlucoseChange}
                        >
                            <option value="fasting">Fasting</option>
                            <option value="before_meal">Before Meal</option>
                            <option value="after_meal">After Meal</option>
                            <option value="bedtime">Bedtime</option>
                            <option value="">Unspecified</option>
                        </select>
                    </div>

                    <button type="submit" disabled={saving || !patientId}>
                        {saving ? 'Saving...' : 'Save Glucose Reading'}
                    </button>

                    {messages}
                </form>
            )}

            {activeTab === 'insulin' && (
                <form onSubmit={handleInsulinSubmit}>
                    <h3>Log Insulin Dose</h3>

                    <div className="form-field">
                        <label htmlFor="insulin-units">
                            Insulin Dose (units)
                        </label>
                        <input
                            id="insulin-units"
                            name="units"
                            type="number"
                            min="0.1"
                            max="100"
                            step="0.1"
                            required
                            value={insulin.units}
                            onChange={handleInsulinChange}
                            placeholder="e.g. 8"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="insulin-type">
                            Insulin Type
                        </label>
                        <select
                            id="insulin-type"
                            name="insulinType"
                            value={insulin.insulinType}
                            onChange={handleInsulinChange}
                        >
                            <option value="rapid">Rapid-acting</option>
                            <option value="short">Short-acting</option>
                            <option value="intermediate">Intermediate-acting</option>
                            <option value="long">Long-acting</option>
                            <option value="premixed">Premixed</option>
                            <option value="">Unspecified</option>
                        </select>
                    </div>

                    <div className="form-field">
                        <label htmlFor="insulin-time">
                            Administration Date and Time
                        </label>
                        <input
                            id="insulin-time"
                            name="administeredAt"
                            type="datetime-local"
                            required
                            value={insulin.administeredAt}
                            onChange={handleInsulinChange}
                        />
                    </div>

                    <button type="submit" disabled={saving || !patientId}>
                        {saving ? 'Saving...' : 'Save Insulin Dose'}
                    </button>

                    {messages}
                </form>
            )}

            {activeTab === 'nutrition' && (
                <form onSubmit={handleNutritionSubmit}>
                    <h3>Log Meal</h3>

                    <div className="form-field">
                        <label htmlFor="meal-description">
                            Meal Description
                        </label>
                        <input
                            id="meal-description"
                            name="description"
                            type="text"
                            required
                            maxLength={500}
                            value={nutrition.description}
                            onChange={handleNutritionChange}
                            placeholder="e.g. Chicken and rice"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="meal-carbs">
                            Carbohydrates (grams, optional)
                        </label>
                        <input
                            id="meal-carbs"
                            name="carbs"
                            type="number"
                            min="0"
                            max="500"
                            step="0.1"
                            value={nutrition.carbs}
                            onChange={handleNutritionChange}
                            placeholder="e.g. 45"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="meal-calories">
                            Calories (kcal, optional)
                        </label>
                        <input
                            id="meal-calories"
                            name="calories"
                            type="number"
                            min="0"
                            max="5000"
                            step="1"
                            value={nutrition.calories}
                            onChange={handleNutritionChange}
                            placeholder="e.g. 500"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="meal-time">
                            Meal Date and Time
                        </label>
                        <input
                            id="meal-time"
                            name="eatenAt"
                            type="datetime-local"
                            required
                            value={nutrition.eatenAt}
                            onChange={handleNutritionChange}
                        />
                    </div>

                    <button type="submit" disabled={saving || !patientId}>
                        {saving ? 'Saving...' : 'Save Meal'}
                    </button>

                    {messages}
                </form>
            )}
        </section>
    );
}
