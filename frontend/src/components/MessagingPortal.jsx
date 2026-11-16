
import { useState } from 'react';

export default function MessagingPortal({ patientId }) {
    const [messages, setMessages] = useState([]);
    const [draft, setDraft] = useState('');

    // Messaging API endpoints have not been implemented yet.
    const sendingAvailable = false;

    function handleSubmit(event) {
        event.preventDefault();

        // Do not create a fake sent message.
        // This will connect to the backend messaging API later.
        if (!sendingAvailable || !patientId) return;
    }

    function formatTimestamp(timestamp) {
        return new Date(timestamp).toLocaleString();
    }

    return (
        <section className="chart-card messaging-portal">
            <div className="messaging-header">
                <div>
                    <h2>Patient-Provider Messaging</h2>
                    <p>
                        Communicate securely with your healthcare team.
                    </p>
                </div>

                <span className="messaging-status">
                    Messaging Unavailable
                </span>
            </div>

            <div className="messaging-conversation">
                {messages.length === 0 ? (
                    <div className="messaging-empty">
                        <h3>No Messages Yet</h3>
                        <p>
                            Your conversation with your healthcare
                            provider will appear here when messaging
                            is connected to the backend.
                        </p>
                    </div>
                ) : (
                    messages.map((message) => (
                        <div
                            key={message.id}
                            className={`message-bubble ${
                                message.sender === 'patient'
                                    ? 'message-sent'
                                    : 'message-received'
                            }`}
                        >
                            <div className="message-sender">
                                {message.sender === 'patient'
                                    ? 'You'
                                    : 'Healthcare Provider'}
                            </div>

                            <p>{message.content}</p>

                            <span className="message-time">
                                {formatTimestamp(message.created_at)}
                            </span>
                        </div>
                    ))
                )}
            </div>

            <form
                className="messaging-composer"
                onSubmit={handleSubmit}
            >
                <label htmlFor="message-draft">
                    New Message
                </label>

                <textarea
                    id="message-draft"
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder="Write a message to your healthcare provider..."
                    rows={4}
                    maxLength={2000}
                />

                <div className="messaging-actions">
                    <span className="message-character-count">
                        {draft.length}/2000 characters
                    </span>

                    <button
                        type="submit"
                        disabled={
                            !sendingAvailable ||
                            !patientId ||
                            !draft.trim()
                        }
                    >
                        Send Message
                    </button>
                </div>
            </form>

            <p className="messaging-notice" role="status">
                Messaging is not yet connected to the backend.
                Messages cannot be sent or received at this time.
            </p>
        </section>
    );
}
