
import { useState } from 'react';

const initialGlucose = {
    value: '',
    measuredAt: '',
    mealContext: 'fasting',
};

const initialInsulin = {
    units: '',
    insulinType: 'short',
    administeredAt: '',
};

const initialNutrition = {
    description: '',
    carbs: '',
    calories: '',
    eatenAt: '',
};

export default function ManualLogging({ patientId }) {
    const [activeTab, setActiveTab] = useState('glucose');

    const [glucose, setGlucose] = useState(initialGlucose);
    const [insulin, setInsulin] = useState(initialInsulin);
    const [nutrition, setNutrition] = useState(initialNutrition);

    // Saving will be enabled when backend POST endpoints are ready.
    const savingAvailable = false;

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
                    onClick={() => setActiveTab('glucose')}
                    aria-pressed={activeTab === 'glucose'}
                >
                    Glucose
                </button>

                <button
                    type="button"
                    onClick={() => setActiveTab('insulin')}
                    aria-pressed={activeTab === 'insulin'}
                >
                    Insulin
                </button>

                <button
                    type="button"
                    onClick={() => setActiveTab('nutrition')}
                    aria-pressed={activeTab === 'nutrition'}
                >
                    Nutrition
                </button>
            </div>

            {activeTab === 'glucose' && (
                <form onSubmit={(event) => event.preventDefault()}>
                    <h3>Log Glucose Reading</h3>

                    <div className="form-field">
                        <label htmlFor="glucose-value">
                            Blood Glucose (mg/dL)
                        </label>
                        <input
                            id="glucose-value"
                            name="value"
                            type="number"
                            min="1"
                            max="600"
                            step="1"
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
                            <option value="other">Other</option>
                        </select>
                    </div>

                    <button type="submit" disabled={!savingAvailable || !patientId}>
                        Save Glucose Reading
                    </button>
                </form>
            )}

            {activeTab === 'insulin' && (
                <form onSubmit={(event) => event.preventDefault()}>
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
                            <option value="short">Short-acting</option>
                            <option value="intermediate">Intermediate-acting</option>
                            <option value="long">Long-acting</option>
                            <option value="other">Other</option>
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

                    <button type="submit" disabled={!savingAvailable || !patientId}>
                        Save Insulin Dose
                    </button>
                </form>
            )}

            {activeTab === 'nutrition' && (
                <form onSubmit={(event) => event.preventDefault()}>
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
                            value={nutrition.description}
                            onChange={handleNutritionChange}
                            placeholder="e.g. Chicken and rice"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="meal-carbs">
                            Carbohydrates (grams)
                        </label>
                        <input
                            id="meal-carbs"
                            name="carbs"
                            type="number"
                            min="0"
                            step="0.1"
                            required
                            value={nutrition.carbs}
                            onChange={handleNutritionChange}
                            placeholder="e.g. 45"
                        />
                    </div>

                    <div className="form-field">
                        <label htmlFor="meal-calories">
                            Calories (kcal)
                        </label>
                        <input
                            id="meal-calories"
                            name="calories"
                            type="number"
                            min="0"
                            step="1"
                            required
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

                    <button type="submit" disabled={!savingAvailable || !patientId}>
                        Save Meal
                    </button>
                </form>
            )}

            <p
                role="status"
                style={{
                    marginTop: '18px',
                    fontSize: '14px',
                    color: '#64748b',
                }}
            >
                Saving is not yet available. The backend must support
                POST requests before records can be stored.
            </p>
        </section>
    );
}
