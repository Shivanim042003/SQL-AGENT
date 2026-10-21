import { useState } from "react";
import "./App.css";

function App() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const askQuestion = async () => {
    if (!question.trim()) {
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: question.trim(),
        }),
      });

      if (!response.ok) {
        throw new Error("Request failed");
      }

      const data = await response.json();

      setAnswer(data.answer);
    } catch (err) {
      setError("Unable to connect to the SQL agent.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && e.ctrlKey) {
      askQuestion();
    }
  };

  return (
    <div className="app">
      <div className="background-glow glow-one"></div>
      <div className="background-glow glow-two"></div>

      <main className="container">
        <header className="header">
          <div className="badge">
            <span className="status-dot"></span>
            AI DATABASE AGENT
          </div>

          <h1>Self-Correcting SQL Agent</h1>

          <p className="subtitle">
            Ask questions about your database using natural language.
            The agent generates, executes, reviews, and corrects SQL automatically.
          </p>
        </header>

        <section className="query-card">
          <div className="card-header">
            <div>
              <h2>Ask your database</h2>
              <p>Enter a natural-language question below.</p>
            </div>
          </div>

          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Example: How many events are in the database?"
            className="question-input"
          />

          <div className="input-footer">
            <span className="shortcut">Ctrl + Enter to run</span>

            <button
              onClick={askQuestion}
              disabled={loading || !question.trim()}
              className="ask-button"
            >
              {loading ? (
                <>
                  <span className="spinner"></span>
                  Thinking...
                </>
              ) : (
                <>
                  Run Query
                  <span className="arrow">→</span>
                </>
              )}
            </button>
          </div>
        </section>

        {error && (
          <section className="error-card">
            <div className="error-icon">!</div>
            <div>
              <h3>Request failed</h3>
              <p>{error}</p>
            </div>
          </section>
        )}

        {loading && (
          <section className="loading-card">
            <div className="loading-line"></div>

            <div className="loading-content">
              <div className="loading-spinner"></div>

              <div>
                <h3>Agent is working...</h3>
                <p>
                  Generating SQL, executing the query, and reviewing the result.
                </p>
              </div>
            </div>
          </section>
        )}

        {answer && !loading && (
          <section className="answer-card">
            <div className="answer-header">
              <div>
                <span className="section-label">RESULT</span>
                <h2>Agent Response</h2>
              </div>

              <span className="success-badge">
                <span className="success-dot"></span>
                Complete
              </span>
            </div>

            <div className="answer-content">
              {answer}
            </div>
          </section>
        )}

        <footer className="footer">
          <span>Self-Correcting SQL Agent</span>
          <span>•</span>
          <span>Powered by LangGraph + PostgreSQL</span>
        </footer>
      </main>
    </div>
  );
}

export default App;