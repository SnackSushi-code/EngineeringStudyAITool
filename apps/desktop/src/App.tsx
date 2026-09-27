import {
  FormEvent,
  useEffect,
  useState,
} from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

type Message = {
  id: number;
  role: "assistant" | "user";
  content: string;
};

type RuntimeHealth = {
  connected: boolean;
  runtimeVersion: string | null;
  message: string;
};

type RuntimeMessage = {
  responseText: string;
  stopReason: string;
  iterations: number;
  providerId: string;
  providerVersion: string;
  model: string;
};

const initialMessages: Message[] = [
  {
    id: 1,
    role: "assistant",
    content:
      "Hello, Nick. I'm Ann-E. My desktop shell is online and I'm connecting this conversation to the Phase 1 intelligence runtime.",
  },
];

const quickActions = [
  {
    label: "Study",
    description: "Open study tools",
    icon: "▣",
  },
  {
    label: "Engineering",
    description: "Engineering workspace",
    icon: "⌬",
  },
  {
    label: "Research",
    description: "Research workspace",
    icon: "⌕",
  },
  {
    label: "Projects",
    description: "Project workspace",
    icon: "◇",
  },
];

function App() {
  const [messages, setMessages] =
    useState<Message[]>(initialMessages);

  const [input, setInput] = useState("");

  const [runtimeConnected, setRuntimeConnected] =
    useState(false);

  const [runtimeVersion, setRuntimeVersion] =
    useState<string | null>(null);

  const [isSending, setIsSending] =
    useState(false);

  useEffect(() => {
    void refreshRuntimeHealth();
  }, []);

  const refreshRuntimeHealth = async () => {
    try {
      const health = await invoke<RuntimeHealth>(
        "runtime_health",
      );

      setRuntimeConnected(health.connected);
      setRuntimeVersion(health.runtimeVersion);
    } catch {
      setRuntimeConnected(false);
      setRuntimeVersion(null);
    }
  };

  const submitMessage = async (
    message: string,
  ) => {
    const trimmedMessage = message.trim();

    if (!trimmedMessage || isSending) {
      return;
    }

    const conversation = messages.map(
      (currentMessage) => ({
        role: currentMessage.role,
        content: currentMessage.content,
      }),
    );

    const userMessage: Message = {
      id: Date.now(),
      role: "user",
      content: trimmedMessage,
    };

    setMessages((currentMessages) => [
      ...currentMessages,
      userMessage,
    ]);

    setInput("");
    setIsSending(true);

    try {
      const result =
        await invoke<RuntimeMessage>(
          "runtime_message",
          {
            userIntent: trimmedMessage,
            conversation,
          },
        );

      const assistantMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content: result.responseText,
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);

      setRuntimeConnected(true);
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now() + 1,
        role: "assistant",
        content:
          "I could not complete the runtime request.\n\n" +
          String(error),
      };

      setMessages((currentMessages) => [
        ...currentMessages,
        errorMessage,
      ]);

      await refreshRuntimeHealth();
    } finally {
      setIsSending(false);
    }
  };

  const handleSubmit = (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    void submitMessage(input);
  };

  const handleQuickAction = (
    label: string,
  ) => {
    void submitMessage(`Open ${label}`);
  };

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <div className="brand">
          <div
            className="brand-mark"
            aria-hidden="true"
          >
            <span />
            <span />
            <span />
          </div>

          <div>
            <div className="brand-name">
              ANN-E
            </div>

            <div className="brand-subtitle">
              Engineering Intelligence
            </div>
          </div>
        </div>

        <div className="topbar-status">
          <span
            className="status-dot"
            style={{
              opacity: runtimeConnected
                ? 1
                : 0.35,
            }}
          />

          <span>
            {runtimeConnected
              ? "Runtime Connected"
              : "Runtime Offline"}
          </span>
        </div>

        <div
          className="window-actions"
          aria-label="Application controls"
        >
          <button
            type="button"
            aria-label="Notifications"
          >
            ◇
          </button>

          <button
            type="button"
            aria-label="Settings"
          >
            ⚙
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <div className="sidebar-section">
            <div className="sidebar-label">
              WORKSPACE
            </div>

            <button
              className="nav-item active"
              type="button"
            >
              <span className="nav-icon">
                ◈
              </span>
              <span>Assistant</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ▣
              </span>
              <span>Study</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ⌬
              </span>
              <span>Engineering</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ⌕
              </span>
              <span>Research</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ◇
              </span>
              <span>Projects</span>
            </button>
          </div>

          <div className="sidebar-section">
            <div className="sidebar-label">
              SYSTEM
            </div>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ◌
              </span>
              <span>Runtime</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ⬡
              </span>
              <span>Colony</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                ⚙
              </span>
              <span>Settings</span>
            </button>
          </div>

          <div className="sidebar-footer">
            <div className="runtime-card">
              <div className="runtime-card-header">
                <span
                  className="runtime-indicator"
                  style={{
                    opacity: runtimeConnected
                      ? 1
                      : 0.35,
                  }}
                />

                <span>Runtime</span>
              </div>

              <strong>
                {runtimeConnected
                  ? "Connected"
                  : "Offline"}
              </strong>

              <span className="runtime-version">
                {runtimeVersion
                  ? `v${runtimeVersion}`
                  : "Phase 1 baseline"}
              </span>
            </div>
          </div>
        </aside>

        <main className="main-content">
          <section className="hero">
            <div
              className="assistant-visual"
              aria-hidden="true"
            >
              <div className="orb-ring ring-one" />
              <div className="orb-ring ring-two" />

              <div className="orb-core">
                <div className="orb-eye left" />
                <div className="orb-eye right" />
                <div className="orb-mouth" />
              </div>
            </div>

            <div className="hero-copy">
              <div className="eyebrow">
                <span className="eyebrow-line" />
                ANN-E CORE
              </div>

              <h1>
                Your engineering
                <span>
                  {" "}
                  intelligence layer.
                </span>
              </h1>

              <p>
                A secure desktop interface for
                study, engineering, research,
                projects, and the intelligence
                runtime underneath.
              </p>
            </div>
          </section>

          <section className="conversation-panel">
            <div className="panel-header">
              <div>
                <span className="panel-eyebrow">
                  CURRENT SESSION
                </span>

                <h2>Assistant</h2>
              </div>

              <span className="session-state">
                <span />
                {isSending
                  ? "Thinking"
                  : runtimeConnected
                    ? "Runtime Connected"
                    : "Shell Ready"}
              </span>
            </div>

            <div className="messages">
              {messages.map((message) => (
                <article
                  className={`message ${
                    message.role === "user"
                      ? "message-user"
                      : "message-assistant"
                  }`}
                  key={message.id}
                >
                  <div className="message-avatar">
                    {message.role === "user"
                      ? "N"
                      : "A"}
                  </div>

                  <div className="message-content">
                    <div className="message-role">
                      {message.role === "user"
                        ? "You"
                        : "Ann-E"}
                    </div>

                    <p>
                      {message.content}
                    </p>
                  </div>
                </article>
              ))}

              {isSending && (
                <article className="message message-assistant">
                  <div className="message-avatar">
                    A
                  </div>

                  <div className="message-content">
                    <div className="message-role">
                      Ann-E
                    </div>

                    <p>
                      Routing your request
                      through the intelligence
                      runtime…
                    </p>
                  </div>
                </article>
              )}
            </div>

            <form
              className="composer"
              onSubmit={handleSubmit}
            >
              <div className="composer-icon">
                ✦
              </div>

              <input
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                placeholder="Ask Ann-E anything..."
                aria-label="Message Ann-E"
                disabled={isSending}
              />

              <button
                className="send-button"
                type="submit"
                disabled={
                  !input.trim() || isSending
                }
              >
                <span>
                  {isSending
                    ? "Working"
                    : "Send"}
                </span>

                <span aria-hidden="true">
                  →
                </span>
              </button>
            </form>
          </section>

          <section className="quick-actions">
            <div className="section-heading">
              <div>
                <span className="panel-eyebrow">
                  QUICK ACCESS
                </span>

                <h2>
                  What are we working on?
                </h2>
              </div>
            </div>

            <div className="quick-grid">
              {quickActions.map((action) => (
                <button
                  className="quick-card"
                  key={action.label}
                  type="button"
                  onClick={() =>
                    handleQuickAction(
                      action.label,
                    )
                  }
                  disabled={isSending}
                >
                  <span className="quick-icon">
                    {action.icon}
                  </span>

                  <span className="quick-copy">
                    <strong>
                      {action.label}
                    </strong>

                    <small>
                      {action.description}
                    </small>
                  </span>

                  <span className="quick-arrow">
                    →
                  </span>
                </button>
              ))}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
