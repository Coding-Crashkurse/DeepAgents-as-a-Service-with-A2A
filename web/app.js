import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.2.0";
import { createRoot } from "https://esm.sh/react-dom@18.2.0/client";
import htm from "https://esm.sh/htm@3.1.1";

import { marked } from "https://esm.sh/marked@12.0.2";
import DOMPurify from "https://esm.sh/dompurify@3.1.6";

const html = htm.bind(React.createElement);

const EXAMPLES = [
  "Explain 4-3 vs 3-4 defense and why cats purr.",
  "Give me 3 training tips for a kitten and a summary of zone coverage.",
  "Summarize nickel defense and how cats show stress.",
];

const STATUS_LABELS = {
  idle: "Idle",
  connecting: "Connecting",
  streaming: "Streaming",
  working: "Working",
  submitted: "Submitted",
  completed: "Completed",
  stopped: "Stopped",
  error: "Error",
};

const STATUS_CLASS = {
  idle: "idle",
  connecting: "live",
  streaming: "live",
  working: "live",
  submitted: "live",
  completed: "done",
  stopped: "idle",
  error: "error",
};

function renderMarkdownSafe(md) {
  if (!md) return "";
  const raw = marked.parse(md, { gfm: true, breaks: true });
  return DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } });
}

function looksLikeMarkdown(text) {
  if (!text) return false;
  // cheap heuristic: headings, bold/italic, code fences, lists
  return /(^#{1,6}\s)|(\*\*.+\*\*)|(```)|(^\s*[-*+]\s)|(^\s*\d+\.\s)/m.test(text);
}

function App() {
  const [text, setText] = useState("");
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("idle");
  const [latest, setLatest] = useState("");
  const [error, setError] = useState("");
  const sourceRef = useRef(null);

  useEffect(() => {
    return () => {
      if (sourceRef.current) sourceRef.current.close();
    };
  }, []);

  const stopStream = () => {
    if (sourceRef.current) {
      sourceRef.current.close();
      sourceRef.current = null;
    }
    setStatus("stopped");
  };

  const startStream = () => {
    const trimmed = text.trim();
    if (!trimmed) return;

    stopStream();
    setEvents([]);
    setLatest("");
    setError("");
    setStatus("connecting");

    const url = `/api/stream?text=${encodeURIComponent(trimmed)}`;
    const source = new EventSource(url);
    sourceRef.current = source;

    source.onopen = () => setStatus("streaming");

    source.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (_err) {
        return;
      }

      if (payload.type === "done") {
        setStatus("completed");
        source.close();
        sourceRef.current = null;
        return;
      }

      if (payload.type === "error") {
        setError(payload.message || "Proxy error");
        setStatus("error");
        source.close();
        sourceRef.current = null;
        return;
      }

      const entry = {
        id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
        type: payload.type || "message",
        state: payload.state || "",
        text: payload.text || "",
        ts: payload.ts || new Date().toISOString(),
      };

      if (entry.text) setLatest(entry.text);
      if (entry.state) setStatus(entry.state);

      setEvents((prev) => [...prev, entry]);
    };

    source.onerror = () => {
      setError("Stream error. Check the proxy and agent server logs.");
      setStatus("error");
      source.close();
      sourceRef.current = null;
    };
  };

  const statusText = STATUS_LABELS[status] || status;
  const statusClass = STATUS_CLASS[status] || "idle";

  const latestHtml = useMemo(() => renderMarkdownSafe(latest), [latest]);

  return html`
    <div className="page">
      <header className="hero">
        <span className="kicker">A2A STREAM CONSOLE</span>
        <h1>Watch DeepAgents step through each tool call in real time.</h1>
        <p>
          The proxy connects to your A2A server and streams every update so you can inspect subagent calls
          and the final answer as they arrive.
        </p>
      </header>

      <section className="stack">
        <div className="card input-card">
          <div className="input-top">
            <div className="input-col">
              <label htmlFor="prompt">Prompt</label>
              <textarea
                id="prompt"
                value=${text}
                placeholder="Ask about football, cats, or both."
                onChange=${(event) => setText(event.target.value)}
              />
            </div>

            <div className="actions-col">
              <div className="button-row">
                <button className="primary" onClick=${startStream} disabled=${!text.trim()}>
                  Start stream
                </button>
                <button className="secondary" onClick=${stopStream}>Stop</button>
                <button
                  className="ghost"
                  onClick=${() => {
                    setEvents([]);
                    setLatest("");
                    setError("");
                    setStatus("idle");
                  }}
                >
                  Clear
                </button>
              </div>

              <div className="meta-row">
                <span className=${`status-pill ${statusClass}`}>${statusText}</span>
                <span className="endpoint">Proxy: <code>/api/stream</code></span>
              </div>
            </div>
          </div>

          <div className="examples">
            <label>Example prompts</label>
            <div className="prompts">
              ${EXAMPLES.map(
                (prompt) => html`
                  <button
                    key=${prompt}
                    className="prompt-chip"
                    onClick=${() => setText(prompt)}
                    type="button"
                  >
                    ${prompt}
                  </button>
                `
              )}
            </div>
          </div>
        </div>

        <div className="card output-card">
          <div className="output-header">
            <strong>Stream output</strong>
          </div>

          ${error ? html`<div className="error-banner">${error}</div>` : null}

          <div className="latest">
            <div className="latest-head">
              <h3>Latest message</h3>
            </div>

            ${latest
              ? html`<div className="markdown" dangerouslySetInnerHTML=${{ __html: latestHtml }}></div>`
              : html`<div className="placeholder">Waiting for updates.</div>`}
          </div>

          <div className="events">
            <div className="events-head">
              <h3>Events</h3>
              <span className="events-count">${events.length}</span>
            </div>

            <div className="events-list">
              ${events.length === 0
                ? html`
                    <div className="event" style=${{ "--i": 0 }}>
                      <div className="event-meta">
                        <span>status</span>
                        <span>ready</span>
                      </div>
                      <p className="event-text">No events yet. Start a stream to see updates.</p>
                    </div>
                  `
                : events.map((item, index) => {
                    const line = item.text || (item.state ? `State: ${item.state}` : "Update");
                    const renderAsMarkdown =
                      item.type === "message" && looksLikeMarkdown(line);

                    if (renderAsMarkdown) {
                      const eventHtml = renderMarkdownSafe(line);
                      return html`
                        <div key=${item.id} className="event" style=${{ "--i": index + 1 }}>
                          <div className="event-meta">
                            <span>${item.type}</span>
                            <span>${new Date(item.ts).toLocaleTimeString()}</span>
                          </div>
                          <div
                            className="event-markdown"
                            dangerouslySetInnerHTML=${{ __html: eventHtml }}
                          ></div>
                        </div>
                      `;
                    }

                    return html`
                      <div key=${item.id} className="event" style=${{ "--i": index + 1 }}>
                        <div className="event-meta">
                          <span>${item.type}</span>
                          <span>${new Date(item.ts).toLocaleTimeString()}</span>
                        </div>
                        <p className="event-text">${line}</p>
                      </div>
                    `;
                  })}
            </div>
          </div>
        </div>
      </section>
    </div>
  `;
}

const root = createRoot(document.getElementById("root"));
root.render(React.createElement(App));
