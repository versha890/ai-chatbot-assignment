
import { useState } from "react";
import { sendMessage } from "./api";
import "./App.css";

const createSessionId = () => crypto.randomUUID();

export default function App() {
  const [sessionId, setSessionId] = useState(createSessionId);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSend(e) {
    e.preventDefault();
    const message = input.trim();
    if (!message || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: message }]);
    setLoading(true);

    try {
      const data = await sendMessage(sessionId, message, systemPrompt);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.reply, metadata: data.metadata },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        { role: "error", content: error.message },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function newChat() {
    setSessionId(createSessionId());
    setMessages([]);
    setInput("");
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">✦ IntelliChat</div>
        <button className="new-chat" onClick={newChat}>+ New Chat</button>
        <div className="side-note">AI-powered assistant<br />Ask anything, learn anything.</div>
        <div className="sidebar-bottom">Powered by Groq AI</div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h2>AI Assistant</h2>
            <span className="online">● Online</span>
          </div>
          <span className="model-pill">GPT OSS 20B</span>
        </header>

        <section className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">✦</div>
              <h1>How can I help you today?</h1>
              <p>Ask a question and let's get started.</p>
              <div className="suggestions">
                {["Explain artificial intelligence", "What is React?", "Give me Python interview tips"].map((q) => (
                  <button key={q} onClick={() => setInput(q)}>{q} ↗</button>
                ))}
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((msg, i) => (
                <div className={`message ${msg.role}`} key={i}>
                  <div className="avatar">
                    {msg.role === "user" ? "You" : "✦"}
                  </div>
                  <div className="message-content">
                    <strong>{msg.role === "user" ? "You" : msg.role === "error" ? "Error" : "Assistant"}</strong>
                    <p data-testid={msg.role === "assistant" ? "assistant-message" : undefined}>
                      {msg.content}
                    </p>

                    {msg.metadata && (
                      <div className="metadata">
                        <span data-testid="meta-source">{msg.metadata.resolution_source}</span>
                        <span data-testid="meta-model">{msg.metadata.model}</span>
                        <span data-testid="meta-latency">{msg.metadata.latency_ms} ms</span>
                        <span data-testid="meta-input-tokens">In: {msg.metadata.input_tokens}</span>
                        <span data-testid="meta-output-tokens">Out: {msg.metadata.output_tokens}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {loading && <div className="typing">✦ Assistant is thinking...</div>}
            </div>
          )}
        </section>

        <div className="composer-area">
          <details className="system-prompt">
            <summary>⚙ Customize system prompt</summary>
            <textarea
              data-testid="system-prompt-input"
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="Optional instructions for the AI..."
            />
          </details>

          <form className="composer" onSubmit={handleSend}>
            <input
              data-testid="chat-input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Message your AI assistant..."
              disabled={loading}
            />
            <button data-testid="send-button" type="submit" disabled={loading || !input.trim()}>
              {loading ? "..." : "Send ↑"}
            </button>
          </form>
          <p className="disclaimer">AI can make mistakes. Verify important information.</p>
        </div>
      </main>
    </div>
  );
}
