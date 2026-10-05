import {
  FormEvent,
  KeyboardEvent,
  useEffect,
  useRef,
  useState,
} from "react";
import { invoke } from "@tauri-apps/api/core";
import "./App.css";

type MessageRole = "assistant" | "user";

type MessageStatus =
  | "pending"
  | "sent"
  | "processing"
  | "completed"
  | "error";

type ConversationMessage = {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string;
  status: MessageStatus;
  requestId: string | null;
  taskId: string | null;
  error: string | null;
};

type RuntimeHealth = {
  connected: boolean;
  runtimeVersion: string | null;
  message: string;
};

type RuntimeSession = {
  sessionId: string;
};

type RuntimeMessage = {
  responseText: string;
  stopReason: string;
  iterations: number;
  providerId: string;
  providerVersion: string;
  model: string;
};

const createMessageId = (): string => {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }

  return `message-${Date.now()}-${Math.random()
    .toString(36)
    .slice(2)}`;
};

const createConversationMessage = (
  role: MessageRole,
  content: string,
  status: MessageStatus = "completed",
): ConversationMessage => ({
  id: createMessageId(),
  role,
  content,
  timestamp: new Date().toISOString(),
  status,
  requestId: null,
  taskId: null,
  error: null,
});

const initialMessages: ConversationMessage[] = [
  {
    id: "initial-assistant-message",
    role: "assistant",
    content:
      "Hello, Nick. I'm Ann-E. My desktop shell is online and I'm connecting this conversation to the Phase 1 intelligence runtime.",
    timestamp: new Date().toISOString(),
    status: "completed",
    requestId: null,
    taskId: null,
    error: null,
  },
];

const quickActions = [
  {
    label: "Study",
    description: "Open study tools",
    icon: "S",
  },
  {
    label: "Engineering",
    description: "Engineering workspace",
    icon: "E",
  },
  {
    label: "Research",
    description: "Research workspace",
    icon: "R",
  },
  {
    label: "Projects",
    description: "Project workspace",
    icon: "P",
  },
];

const formatMessageTime = (
  timestamp: string,
): string => {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
};

const getSessionState = (
  isSending: boolean,
  runtimeConnected: boolean,
): string => {
  if (isSending) {
    return "Thinking";
  }

  if (runtimeConnected) {
    return "Runtime Connected";
  }

  return "Shell Ready";
};

function App() {
  const [messages, setMessages] =
    useState<ConversationMessage[]>(
      initialMessages,
    );

  const [input, setInput] = useState("");

  const [runtimeConnected, setRuntimeConnected] =
    useState(false);

  const [sessionId, setSessionId] =
    useState<string | null>(null);

  const [runtimeVersion, setRuntimeVersion] =
    useState<string | null>(null);

  const [isSending, setIsSending] =
    useState(false);

  const inputRef =
    useRef<HTMLInputElement | null>(null);

  const messagesEndRef =
    useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    void initializeRuntimeSession();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "end",
    });
  }, [messages, isSending]);

  useEffect(() => {
    if (!isSending) {
      inputRef.current?.focus();
    }
  }, [isSending]);

  const initializeRuntimeSession = async () => {
    try {
      const health = await invoke<RuntimeHealth>(
        "runtime_health",
      );

      setRuntimeConnected(health.connected);
      setRuntimeVersion(health.runtimeVersion);

      if (!health.connected) {
        setSessionId(null);
        return;
      }

      const session = await invoke<RuntimeSession>(
        "runtime_create_session",
      );

      setSessionId(session.sessionId);
    } catch {
      setRuntimeConnected(false);
      setRuntimeVersion(null);
      setSessionId(null);
    }
  };
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

    const submittedMessage = trimmedMessage;

    if (!sessionId) {
      try {
        const session = await invoke<RuntimeSession>(
          "runtime_create_session",
        );

        setSessionId(session.sessionId);
      } catch (error) {
        const errorText = String(error);

        const errorMessage =
          createConversationMessage(
            "assistant",
            "I could not create a runtime conversation session.",
            "error",
          );

        errorMessage.error = errorText;

        setMessages((currentMessages) => [
          ...currentMessages,
          errorMessage,
        ]);

        await refreshRuntimeHealth();
        return;
      }
    }

    const userMessage =
      createConversationMessage(
        "user",
        submittedMessage,
        "sent",
      );

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
            userIntent: submittedMessage,
            sessionId: sessionId ?? "",
          },
        );

      const assistantMessage =
        createConversationMessage(
          "assistant",
          result.responseText,
          "completed",
        );

      setMessages((currentMessages) => [
        ...currentMessages,
        assistantMessage,
      ]);

      setRuntimeConnected(true);
    } catch (error) {
      const errorText = String(error);

      const errorMessage =
        createConversationMessage(
          "assistant",
          "I could not complete the runtime request.",
          "error",
        );

      errorMessage.error = errorText;

      setMessages((currentMessages) => [
        ...currentMessages,
        errorMessage,
      ]);

      setInput(submittedMessage);

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

  const handleInputKeyDown = (
    event: KeyboardEvent<HTMLInputElement>,
  ) => {
    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();

    if (!isSending && input.trim()) {
      void submitMessage(input);
    }
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

        <div
          className={`topbar-status ${
            runtimeConnected
              ? "status-connected"
              : "status-disconnected"
          }`}
        >
          <span className="status-dot" />

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
            N
          </button>

          <button
            type="button"
            aria-label="Settings"
          >
            S
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
                A
              </span>

              <span>Assistant</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                S
              </span>

              <span>Study</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                E
              </span>

              <span>Engineering</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                R
              </span>

              <span>Research</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                P
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
                R
              </span>

              <span>Runtime</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                C
              </span>

              <span>Colony</span>
            </button>

            <button
              className="nav-item"
              type="button"
            >
              <span className="nav-icon">
                S
              </span>

              <span>Settings</span>
            </button>
          </div>

          <div className="sidebar-footer">
            <div className="runtime-card">
              <div className="runtime-card-header">
                <span
                  className={`runtime-indicator ${
                    runtimeConnected
                      ? "indicator-connected"
                      : "indicator-disconnected"
                  }`}
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
                Your engineering{" "}
                <span>
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
                <span
                  className={
                    isSending
                      ? "session-dot thinking"
                      : runtimeConnected
                        ? "session-dot connected"
                        : "session-dot offline"
                  }
                />

                {getSessionState(
                  isSending,
                  runtimeConnected,
                )}
              </span>
            </div>

            <div
              className="messages"
              aria-live="polite"
              aria-label="Conversation"
            >
              {messages.map((message) => (
                <article
                  className={`message ${
                    message.role === "user"
                      ? "message-user"
                      : "message-assistant"
                  } ${
                    message.status === "error"
                      ? "message-error"
                      : ""
                  }`}
                  key={message.id}
                >
                  <div className="message-avatar">
                    {message.role === "user"
                      ? "N"
                      : "A"}
                  </div>

                  <div className="message-content">
                    <div className="message-meta">
                      <span className="message-role">
                        {message.role === "user"
                          ? "You"
                          : "Ann-E"}
                      </span>

                      <time
                        dateTime={
                          message.timestamp
                        }
                      >
                        {formatMessageTime(
                          message.timestamp,
                        )}
                      </time>
                    </div>

                    <p>{message.content}</p>

                    {message.error && (
                      <div className="message-error-detail">
                        {message.error}
                      </div>
                    )}

                    {message.status ===
                      "error" && (
                      <div className="message-status">
                        Runtime request failed
                      </div>
                    )}
                  </div>
                </article>
              ))}

              {isSending && (
                <article className="message message-assistant">
                  <div className="message-avatar">
                    A
                  </div>

                  <div className="message-content">
                    <div className="message-meta">
                      <span className="message-role">
                        Ann-E
                      </span>

                      <span className="message-processing">
                        Processing
                      </span>
                    </div>

                    <p className="thinking-text">
                      Routing your request
                      through the intelligence
                      runtime
                      <span className="thinking-dots">
                        ...
                      </span>
                    </p>
                  </div>
                </article>
              )}

              <div
                ref={messagesEndRef}
                aria-hidden="true"
              />
            </div>

            <form
              className="composer"
              onSubmit={handleSubmit}
            >
              <div
                className="composer-icon"
                aria-hidden="true"
              >
                +
              </div>

              <input
                ref={inputRef}
                value={input}
                onChange={(event) =>
                  setInput(event.target.value)
                }
                onKeyDown={handleInputKeyDown}
                placeholder="Ask Ann-E anything..."
                aria-label="Message Ann-E"
                disabled={isSending}
                autoComplete="off"
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

                  <span
                    className="quick-arrow"
                    aria-hidden="true"
                  >
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
