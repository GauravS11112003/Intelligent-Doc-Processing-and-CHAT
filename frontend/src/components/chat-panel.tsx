"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Bot,
  User,
  Trash2,
  Sparkles,
  FileText,
  ListChecks,
  BarChart3,
  HelpCircle,
  Copy,
  Check,
  Plus,
  MessageSquare,
  ChevronDown,
  Clock,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import ReactMarkdown from "react-markdown";

const API_URL = "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Message {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  timestamp?: string; // ISO string — serialisable for localStorage
}

interface ConversationSession {
  id: string;
  documentId: string;
  title: string;
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

interface ChatPanelProps {
  documentId: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const SUGGESTED_QUESTIONS = [
  {
    icon: FileText,
    label: "Summarize",
    question: "Give me a comprehensive summary of this document.",
  },
  {
    icon: ListChecks,
    label: "Key Points",
    question: "What are the main key points and findings in this document?",
  },
  {
    icon: BarChart3,
    label: "Data & Numbers",
    question: "What important numbers, dates, or statistics are mentioned?",
  },
  {
    icon: HelpCircle,
    label: "Explain",
    question: "Explain the main topic of this document in simple terms.",
  },
];

const THINKING_STATES = [
  "Thinking",
  "Analyzing your document",
  "Finding relevant context",
  "Drafting a response",
];

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------
function storageKey(documentId: string) {
  return `chat_sessions_${documentId}`;
}

function loadSessions(documentId: string): ConversationSession[] {
  try {
    const raw = localStorage.getItem(storageKey(documentId));
    return raw ? (JSON.parse(raw) as ConversationSession[]) : [];
  } catch {
    return [];
  }
}

function saveSessions(documentId: string, sessions: ConversationSession[]) {
  try {
    localStorage.setItem(storageKey(documentId), JSON.stringify(sessions));
  } catch {
    // localStorage quota exceeded — silently ignore
  }
}

function createNewSession(documentId: string): ConversationSession {
  return {
    id: crypto.randomUUID(),
    documentId,
    title: "New conversation",
    messages: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
}

function deriveTitle(messages: Message[]): string {
  const first = messages.find((m) => m.role === "user");
  if (!first) return "New conversation";
  return first.content.length > 50
    ? first.content.slice(0, 50) + "…"
    : first.content;
}

function formatRelativeTime(iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(ms / 60_000);
  if (mins < 1) return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export function ChatPanel({ documentId }: ChatPanelProps) {
  // Sessions
  const [sessions, setSessions] = useState<ConversationSession[]>(() =>
    loadSessions(documentId)
  );
  const [activeSessionId, setActiveSessionId] = useState<string>(() => {
    const existing = loadSessions(documentId);
    return existing.length > 0 ? existing[0].id : "";
  });
  const [showHistory, setShowHistory] = useState(false);

  // Chat state
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isCloud, setIsCloud] = useState(true);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [thinkingStep, setThinkingStep] = useState(0);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const historyPanelRef = useRef<HTMLDivElement>(null);

  // Derive active session
  const activeSession =
    sessions.find((s) => s.id === activeSessionId) ?? null;
  const messages = activeSession?.messages ?? [];

  // Persist whenever sessions change
  useEffect(() => {
    saveSessions(documentId, sessions);
  }, [sessions, documentId]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Thinking animation
  useEffect(() => {
    if (!isLoading) {
      setThinkingStep(0);
      return;
    }
    const id = window.setInterval(() => {
      setThinkingStep((prev) => (prev + 1) % THINKING_STATES.length);
    }, 1300);
    return () => window.clearInterval(id);
  }, [isLoading]);

  // Close history panel on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (
        historyPanelRef.current &&
        !historyPanelRef.current.contains(e.target as Node)
      ) {
        setShowHistory(false);
      }
    }
    if (showHistory) {
      document.addEventListener("mousedown", handleClick);
    }
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showHistory]);

  // ------------------------------------------------------------------
  // Session management
  // ------------------------------------------------------------------
  const startNewSession = useCallback(() => {
    const session = createNewSession(documentId);
    setSessions((prev) => [session, ...prev]);
    setActiveSessionId(session.id);
    setShowHistory(false);
    setInput("");
    textareaRef.current?.focus();
  }, [documentId]);

  const switchSession = useCallback((id: string) => {
    setActiveSessionId(id);
    setShowHistory(false);
  }, []);

  const deleteSession = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      setSessions((prev) => {
        const next = prev.filter((s) => s.id !== id);
        if (activeSessionId === id) {
          if (next.length > 0) setActiveSessionId(next[0].id);
          else setActiveSessionId("");
        }
        return next;
      });
    },
    [activeSessionId]
  );

  const clearCurrentChat = useCallback(() => {
    setSessions((prev) =>
      prev.map((s) =>
        s.id === activeSessionId
          ? { ...s, messages: [], title: "New conversation", updatedAt: new Date().toISOString() }
          : s
      )
    );
  }, [activeSessionId]);

  // ------------------------------------------------------------------
  // Ensure there is always at least one session
  // ------------------------------------------------------------------
  useEffect(() => {
    if (sessions.length === 0 || !activeSessionId) {
      const session = createNewSession(documentId);
      setSessions([session]);
      setActiveSessionId(session.id);
    }
  }, [sessions.length, activeSessionId, documentId]);

  // ------------------------------------------------------------------
  // Send message
  // ------------------------------------------------------------------
  const sendMessage = async (overrideMessage?: string) => {
    const text = (overrideMessage ?? input).trim();
    if (!text || isLoading) return;

    // Ensure there is an active session
    let sessionId = activeSessionId;
    if (!sessionId) {
      const session = createNewSession(documentId);
      setSessions((prev) => [session, ...prev]);
      setActiveSessionId(session.id);
      sessionId = session.id;
    }

    const userMsg: Message = {
      role: "user",
      content: text,
      timestamp: new Date().toISOString(),
    };

    // Optimistically append user message and capture current history
    let currentHistory: Message[] = [];
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        currentHistory = s.messages;
        const next = [...s.messages, userMsg];
        return {
          ...s,
          messages: next,
          title: deriveTitle(next),
          updatedAt: new Date().toISOString(),
        };
      })
    );

    if (!overrideMessage) setInput("");
    setIsLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: documentId,
          message: text,
          mode: isCloud ? "cloud" : "local",
          // Send the history BEFORE the current user message so the model
          // can reference prior turns in this conversation.
          conversation_history: currentHistory.map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail ?? "Request failed");
      }

      const data = await res.json();
      const assistantMsg: Message = {
        role: "assistant",
        content: data.response,
        sources: data.sources,
        timestamp: new Date().toISOString(),
      };

      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== sessionId) return s;
          return {
            ...s,
            messages: [...s.messages, assistantMsg],
            updatedAt: new Date().toISOString(),
          };
        })
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      const errorMsg: Message = {
        role: "assistant",
        content: `Error: ${msg}`,
        timestamp: new Date().toISOString(),
      };
      setSessions((prev) =>
        prev.map((s) =>
          s.id === sessionId
            ? { ...s, messages: [...s.messages, errorMsg], updatedAt: new Date().toISOString() }
            : s
        )
      );
    } finally {
      setIsLoading(false);
      textareaRef.current?.focus();
    }
  };

  const copyToClipboard = async (text: string, idx: number) => {
    await navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  return (
    <div className="flex flex-col h-full bg-gradient-to-b from-background to-muted/20">
      {/* ── Top bar ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b bg-background/80 backdrop-blur-sm shrink-0 gap-2 relative z-30">
        {/* Session selector */}
        <div className="relative flex-1 min-w-0" ref={historyPanelRef}>
          <button
            onClick={() => setShowHistory((v) => !v)}
            className="flex items-center gap-1.5 max-w-[220px] px-2.5 py-1.5 rounded-lg hover:bg-muted/60 transition-colors text-left w-full"
          >
            <MessageSquare className="size-3.5 text-muted-foreground shrink-0" />
            <span className="text-[12px] font-medium truncate text-foreground/80">
              {activeSession?.title ?? "New conversation"}
            </span>
            <ChevronDown
              className={`size-3 text-muted-foreground shrink-0 transition-transform ${
                showHistory ? "rotate-180" : ""
              }`}
            />
          </button>

          {/* History dropdown */}
          {showHistory && (
            <div className="absolute top-full left-0 mt-1 w-72 bg-popover border rounded-xl shadow-xl z-50 overflow-hidden">
              <div className="flex items-center justify-between px-3 py-2 border-b">
                <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
                  Conversations
                </span>
                <button
                  onClick={startNewSession}
                  className="flex items-center gap-1 text-[11px] font-medium text-primary hover:text-primary/80 transition-colors"
                >
                  <Plus className="size-3" />
                  New chat
                </button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                {sessions.length === 0 ? (
                  <p className="text-[12px] text-muted-foreground text-center py-6">
                    No conversations yet
                  </p>
                ) : (
                  sessions.map((s) => (
                    <div
                      key={s.id}
                      onClick={() => switchSession(s.id)}
                      className={`group flex items-start gap-2 px-3 py-2.5 cursor-pointer hover:bg-muted/50 transition-colors ${
                        s.id === activeSessionId ? "bg-primary/5" : ""
                      }`}
                    >
                      <MessageSquare
                        className={`size-3.5 mt-0.5 shrink-0 ${
                          s.id === activeSessionId
                            ? "text-primary"
                            : "text-muted-foreground"
                        }`}
                      />
                      <div className="flex-1 min-w-0">
                        <p
                          className={`text-[12px] font-medium truncate ${
                            s.id === activeSessionId
                              ? "text-primary"
                              : "text-foreground/80"
                          }`}
                        >
                          {s.title}
                        </p>
                        <p className="text-[10px] text-muted-foreground flex items-center gap-1 mt-0.5">
                          <Clock className="size-2.5" />
                          {formatRelativeTime(s.updatedAt)}
                          {s.messages.length > 0 && (
                            <span className="ml-1">
                              · {Math.ceil(s.messages.length / 2)} turn
                              {Math.ceil(s.messages.length / 2) !== 1 ? "s" : ""}
                            </span>
                          )}
                        </p>
                      </div>
                      <button
                        onClick={(e) => deleteSession(s.id, e)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                        title="Delete conversation"
                      >
                        <Trash2 className="size-3" />
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Model toggle + controls */}
        <div className="flex items-center gap-3 shrink-0">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
              isCloud
                ? "bg-blue-500/10 text-blue-600"
                : "bg-purple-500/10 text-purple-600"
            }`}
          >
            <Sparkles className="size-3" />
            {isCloud ? "Gemini 2.0 Flash" : "Qwen3"}
          </div>

          {messages.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              onClick={clearCurrentChat}
              className="h-7 text-xs text-muted-foreground hover:text-destructive gap-1"
            >
              <Trash2 className="size-3" />
              Clear
            </Button>
          )}

          <Button
            variant="ghost"
            size="sm"
            onClick={startNewSession}
            className="h-7 text-xs text-muted-foreground gap-1"
            title="Start new conversation"
          >
            <Plus className="size-3" />
            New
          </Button>

          <div className="flex items-center gap-2 pl-3 border-l">
            <Label
              htmlFor="chat-model-toggle"
              className={`text-[11px] font-medium cursor-pointer transition-colors ${
                !isCloud ? "text-purple-600" : "text-muted-foreground"
              }`}
            >
              Local
            </Label>
            <Switch
              id="chat-model-toggle"
              checked={isCloud}
              onCheckedChange={setIsCloud}
              className="scale-90"
            />
            <Label
              htmlFor="chat-model-toggle"
              className={`text-[11px] font-medium cursor-pointer transition-colors ${
                isCloud ? "text-blue-600" : "text-muted-foreground"
              }`}
            >
              Cloud
            </Label>
          </div>
        </div>
      </div>

      {/* ── Messages area ───────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-4 custom-scrollbar">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full select-none animate-fade-in">
            <div className="relative mb-6">
              <div className="size-16 rounded-2xl bg-gradient-to-br from-primary/20 to-primary/5 flex items-center justify-center">
                <Bot className="size-8 text-primary/60" />
              </div>
              <div className="absolute -bottom-1 -right-1 size-5 rounded-full bg-emerald-500 flex items-center justify-center ring-2 ring-background">
                <Sparkles className="size-2.5 text-white" />
              </div>
            </div>

            <h3 className="text-lg font-semibold mb-1">Document Assistant</h3>
            <p className="text-sm text-muted-foreground mb-6 text-center max-w-sm">
              Ask anything about your document. I use RAG to find the most
              relevant sections and provide accurate, context-aware answers.
            </p>

            <div className="w-full max-w-lg grid grid-cols-2 gap-2">
              {SUGGESTED_QUESTIONS.map((sq) => (
                <button
                  key={sq.label}
                  onClick={() => sendMessage(sq.question)}
                  className="flex items-start gap-2.5 p-3 rounded-xl border bg-background hover:bg-accent hover:border-primary/20 transition-all duration-200 text-left group"
                >
                  <div className="size-7 rounded-lg bg-primary/8 flex items-center justify-center shrink-0 group-hover:bg-primary/15 transition-colors">
                    <sq.icon className="size-3.5 text-primary/70" />
                  </div>
                  <div>
                    <span className="text-xs font-semibold block">
                      {sq.label}
                    </span>
                    <span className="text-[11px] text-muted-foreground leading-tight line-clamp-2">
                      {sq.question}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-1 max-w-3xl mx-auto">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex gap-3 animate-fade-in-up ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
                style={{ animationDelay: `${Math.min(idx * 50, 200)}ms` }}
              >
                {msg.role === "assistant" && (
                  <div className="size-7 rounded-lg bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center shrink-0 mt-1">
                    <Bot className="size-3.5 text-primary" />
                  </div>
                )}

                <div className="group relative max-w-[85%]">
                  <div
                    className={`rounded-2xl px-4 py-2.5 text-[13px] leading-relaxed ${
                      msg.role === "user"
                        ? "bg-primary text-primary-foreground rounded-br-md"
                        : "bg-card border shadow-sm rounded-bl-md"
                    }`}
                  >
                    {msg.role === "assistant" ? (
                      <div className="chat-markdown">
                        <ReactMarkdown
                          components={{
                            code({ className, children, ...props }: any) {
                              const match = /language-(\w+)/.exec(className || "");
                              if (match && match[1] === "thinking") {
                                return (
                                  <div className="bg-muted/40 border-l-2 border-primary/40 pl-3 pr-2 py-2 mb-3 rounded-r-md text-[11px] text-muted-foreground italic font-mono whitespace-pre-wrap">
                                    <div className="font-semibold mb-1 flex items-center gap-1.5 not-italic text-foreground/70">
                                      <Bot className="size-3" /> Model Thinking Process
                                    </div>
                                    {String(children).replace(/\n$/, "")}
                                  </div>
                                );
                              }
                              return (
                                <code className={className} {...props}>
                                  {children}
                                </code>
                              );
                            },
                          }}
                        >
                          {msg.content.replace(/<think>\n?/gi, "```thinking\n").replace(/<\/think>\n?/gi, "```\n\n")}
                        </ReactMarkdown>
                      </div>
                    ) : (
                      <span className="whitespace-pre-wrap">{msg.content}</span>
                    )}
                  </div>

                  {msg.sources && msg.sources.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1.5 ml-1">
                      {msg.sources.map((s, i) => (
                        <Badge
                          key={i}
                          variant="secondary"
                          className="text-[10px] h-5 px-1.5 bg-primary/5 text-primary/70 hover:bg-primary/10 border-0"
                        >
                          {s}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {msg.role === "assistant" && (
                    <button
                      onClick={() => copyToClipboard(msg.content, idx)}
                      className="absolute -bottom-1 right-2 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded-md hover:bg-muted text-muted-foreground"
                      title="Copy message"
                    >
                      {copiedIdx === idx ? (
                        <Check className="size-3 text-emerald-500" />
                      ) : (
                        <Copy className="size-3" />
                      )}
                    </button>
                  )}

                  {msg.timestamp && (
                    <span
                      className={`text-[10px] text-muted-foreground/50 mt-0.5 block ${
                        msg.role === "user" ? "text-right mr-1" : "ml-1"
                      }`}
                    >
                      {new Date(msg.timestamp).toLocaleTimeString([], {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </span>
                  )}
                </div>

                {msg.role === "user" && (
                  <div className="size-7 rounded-lg bg-primary flex items-center justify-center shrink-0 mt-1">
                    <User className="size-3.5 text-primary-foreground" />
                  </div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="flex gap-3 animate-fade-in">
                <div className="size-7 rounded-lg bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center">
                  <Bot className="size-3.5 text-primary" />
                </div>
                <div className="bg-card border shadow-sm rounded-2xl rounded-bl-md px-4 py-3 min-w-[210px]">
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="font-medium text-foreground/80 transition-all duration-300">
                      {THINKING_STATES[thinkingStep]}
                    </span>
                    <div className="flex items-center gap-1">
                      {[0, 0.14, 0.28].map((delay, i) => (
                        <div
                          key={i}
                          className="size-1.5 rounded-full bg-primary/50"
                          style={{
                            animation: `bounce-dot 1.1s ease-in-out ${delay}s infinite`,
                          }}
                        />
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* ── Input area ──────────────────────────────────────────────── */}
      <div className="p-3 border-t bg-background shrink-0">
        <div className="max-w-3xl mx-auto">
          <div className="flex gap-2 items-end bg-muted/30 rounded-xl border p-1.5 focus-within:border-primary/30 focus-within:bg-background transition-colors">
            <Textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a question about your document…"
              className="min-h-[40px] max-h-[120px] resize-none text-sm border-0 bg-transparent shadow-none focus-visible:ring-0 px-2.5"
              rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
            <Button
              size="icon"
              onClick={() => sendMessage()}
              disabled={isLoading || !input.trim()}
              className="shrink-0 size-8 rounded-lg"
            >
              <Send className="size-3.5" />
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground/50 text-center mt-1.5">
            Press Enter to send · Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}
