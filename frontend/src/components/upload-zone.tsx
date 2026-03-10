"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  Upload,
  FileText,
  Loader2,
  Sparkles,
  MessageSquare,
  TableProperties,
  CheckCircle2,
  AlertCircle,
  Brain,
  ScanSearch,
  Zap,
} from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";

const API_URL = "http://localhost:8000";

interface UploadZoneProps {
  onUploadSuccess: (documentId: string, filename: string) => void;
}

interface ProgressEvent {
  stage: string;
  message: string;
  progress: number;
  current_page?: number;
  total_pages?: number;
  total_chunks?: number;
  embedded_chunks?: number;
  document_id?: string;
  filename?: string;
  page_count?: number;
}

export function UploadZone({ onUploadSuccess }: UploadZoneProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [progressDetails, setProgressDetails] = useState<{
    currentPage?: number;
    totalPages?: number;
    stage?: string;
  }>({});
  const [error, setError] = useState<string | null>(null);
  const [deepScan, setDeepScan] = useState(false);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setIsUploading(true);
      setError(null);
      setUploadProgress("Uploading document...");
      setProgressPercent(0);
      setProgressDetails({});

      const formData = new FormData();
      formData.append("file", file);

      try {
        const url = deepScan
          ? `${API_URL}/upload-stream?deep_scan=true`
          : `${API_URL}/upload-stream`;
        const response = await fetch(url, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const err = await response.json().catch(() => null);
          throw new Error(err?.detail || "Upload failed");
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("Failed to read response stream");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const data: ProgressEvent = JSON.parse(line.slice(6));

                setProgressPercent(data.progress);
                setUploadProgress(data.message);
                setProgressDetails({
                  currentPage: data.current_page,
                  totalPages: data.total_pages,
                  stage: data.stage,
                });

                if (data.stage === "complete" && data.document_id) {
                  onUploadSuccess(data.document_id, data.filename || file.name);
                } else if (data.stage === "error") {
                  throw new Error(data.message);
                }
              } catch {
                // Ignore parse errors for incomplete JSON
              }
            }
          }
        }
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : "Failed to upload file";
        setError(message);
      } finally {
        setIsUploading(false);
        setUploadProgress("");
        setProgressPercent(0);
        setProgressDetails({});
      }
    },
    [onUploadSuccess, deepScan]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "application/pdf": [".pdf"] },
    maxFiles: 1,
    disabled: isUploading,
  });

  const getStageInfo = () => {
    const stage = progressDetails.stage;
    if (stage === "extracting") {
      return { icon: FileText, color: "text-blue-500", label: "Extracting Text", bg: "from-blue-500/20 to-blue-500/5" };
    } else if (stage === "chunking") {
      return { icon: FileText, color: "text-purple-500", label: "Chunking", bg: "from-purple-500/20 to-purple-500/5" };
    } else if (stage === "embedding") {
      return { icon: Sparkles, color: "text-amber-500", label: "Generating Embeddings", bg: "from-amber-500/20 to-amber-500/5" };
    } else if (stage === "finalizing") {
      return { icon: CheckCircle2, color: "text-emerald-500", label: "Finalizing", bg: "from-emerald-500/20 to-emerald-500/5" };
    }
    return { icon: Loader2, color: "text-primary", label: "Processing", bg: "from-primary/20 to-primary/5" };
  };

  const stageInfo = getStageInfo();
  const StageIcon = stageInfo.icon;

  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-56px)] bg-gradient-to-b from-background via-background to-muted/30">
      <div className="w-full max-w-2xl mx-auto px-8 py-12">
        {/* Hero section */}
        <div className="text-center mb-10 animate-fade-in">
          <div className="inline-flex items-center gap-2 rounded-full bg-primary/8 border border-primary/15 px-4 py-1.5 text-xs font-medium text-primary mb-5">
            <Sparkles className="size-3" />
            AI-Powered Document Intelligence
          </div>
          <h2 className="text-3xl font-bold tracking-tight mb-3 bg-gradient-to-r from-foreground to-foreground/70 bg-clip-text text-transparent">
            Upload a Document to Begin
          </h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto leading-relaxed">
            Chat with your PDF using RAG or extract structured data with a
            custom schema — powered by Qwen &amp; Gemini&nbsp;2.0&nbsp;Flash.
          </p>
        </div>

        {/* Drop zone */}
        <div
          {...getRootProps()}
          className={`
            relative border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer
            transition-all duration-300
            ${
              isDragActive
                ? "border-primary bg-primary/5 scale-[1.01] shadow-lg shadow-primary/10"
                : "border-border hover:border-primary/40 hover:bg-muted/30 hover:shadow-md"
            }
            ${isUploading ? "pointer-events-none" : ""}
          `}
        >
          <input {...getInputProps()} />
          <div className="flex flex-col items-center gap-4">
            {isUploading ? (
              <>
                <div className="relative">
                  <div className={`size-16 rounded-2xl bg-gradient-to-br ${stageInfo.bg} flex items-center justify-center`}>
                    <StageIcon
                      className={`size-7 ${stageInfo.color} ${
                        progressDetails.stage !== "finalizing" ? "animate-pulse" : ""
                      }`}
                    />
                  </div>
                  <svg
                    className="absolute -inset-1 size-[calc(100%+8px)] -rotate-90"
                    viewBox="0 0 100 100"
                  >
                    <circle
                      cx="50"
                      cy="50"
                      r="46"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3"
                      className="text-muted/30"
                    />
                    <circle
                      cx="50"
                      cy="50"
                      r="46"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="3"
                      strokeDasharray={`${progressPercent * 2.89} 289`}
                      strokeLinecap="round"
                      className="text-primary transition-all duration-500"
                    />
                  </svg>
                </div>
                <div className="space-y-2.5 w-full max-w-xs">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold">{stageInfo.label}</span>
                    <span className="text-muted-foreground tabular-nums">{progressPercent}%</span>
                  </div>
                  <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-primary to-primary/70 transition-all duration-500 ease-out rounded-full"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {uploadProgress}
                  </p>
                  {progressDetails.currentPage && progressDetails.totalPages && (
                    <p className="text-[11px] text-muted-foreground/60">
                      Page {progressDetails.currentPage} of {progressDetails.totalPages}
                    </p>
                  )}
                </div>
              </>
            ) : (
              <>
                <div className="size-14 rounded-2xl bg-gradient-to-br from-primary/15 to-primary/5 flex items-center justify-center group-hover:from-primary/20 transition-colors">
                  <Upload className="size-6 text-primary" />
                </div>
                <div>
                  <p className="text-base font-semibold">
                    {isDragActive
                      ? "Drop your PDF here"
                      : "Drag & drop a PDF, or click to browse"}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Supports PDF files up to 50 MB — text-based and scanned (OCR)
                  </p>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Deep Scan toggle */}
        {!isUploading && (
          <div className="mt-4 flex items-center justify-center gap-3">
            <div className="flex items-center gap-2 px-4 py-2 rounded-xl border bg-background/80">
              <Zap className={`size-3.5 transition-colors ${!deepScan ? "text-emerald-500" : "text-muted-foreground/50"}`} />
              <Label
                htmlFor="deep-scan-toggle"
                className={`text-[11px] font-medium cursor-pointer transition-colors ${!deepScan ? "text-emerald-600" : "text-muted-foreground"}`}
              >
                Fast Scan
              </Label>
              <Switch
                id="deep-scan-toggle"
                checked={deepScan}
                onCheckedChange={setDeepScan}
                className="scale-90"
              />
              <Label
                htmlFor="deep-scan-toggle"
                className={`text-[11px] font-medium cursor-pointer transition-colors ${deepScan ? "text-amber-600" : "text-muted-foreground"}`}
              >
                Deep Scan
              </Label>
              <ScanSearch className={`size-3.5 transition-colors ${deepScan ? "text-amber-500" : "text-muted-foreground/50"}`} />
            </div>
            {deepScan && (
              <p className="text-[10px] text-amber-600/80 max-w-[180px] leading-tight">
                OCRs embedded images within pages — slower but captures text inside diagrams &amp; tables
              </p>
            )}
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 bg-destructive/5 border border-destructive/20 text-destructive rounded-xl text-xs text-center font-medium flex items-center justify-center gap-2 animate-fade-in">
            <AlertCircle className="size-3.5" />
            {error}
          </div>
        )}

        {/* Feature cards */}
        <div className="grid grid-cols-3 gap-3 mt-8">
          {[
            {
              icon: Brain,
              title: "Smart OCR",
              desc: "Auto-detects scanned pages and applies OCR",
              color: "text-blue-500 bg-blue-500/8",
            },
            {
              icon: MessageSquare,
              title: "RAG Chat",
              desc: "Context-aware Q&A with source references",
              color: "text-emerald-500 bg-emerald-500/8",
            },
            {
              icon: TableProperties,
              title: "Schema Extraction",
              desc: "Define fields, get structured JSON/CSV",
              color: "text-purple-500 bg-purple-500/8",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="flex flex-col items-center text-center p-4 rounded-xl border bg-background/80 hover:bg-background hover:shadow-sm transition-all duration-200"
            >
              <div className={`size-9 rounded-lg ${f.color} flex items-center justify-center mb-2.5`}>
                <f.icon className="size-4" />
              </div>
              <p className="text-xs font-semibold mb-0.5">{f.title}</p>
              <p className="text-[11px] text-muted-foreground leading-tight">{f.desc}</p>
            </div>
          ))}
        </div>

        {/* Tech stack badges */}
        <div className="flex items-center justify-center gap-2 mt-6 flex-wrap">
          {["PyMuPDF", "Tesseract OCR", "ChromaDB", "LangChain", "Instructor"].map((tech) => (
            <span
              key={tech}
              className="px-2.5 py-1 rounded-full bg-muted/50 text-[10px] text-muted-foreground font-medium"
            >
              {tech}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
