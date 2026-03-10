"use client";

import { FileText, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const API_URL = "http://localhost:8000";

interface PdfViewerProps {
  documentId: string;
  filename: string;
}

export function PdfViewer({ documentId, filename }: PdfViewerProps) {
  const pdfUrl = `${API_URL}/files/${documentId}.pdf`;

  const openInNewTab = () => {
    window.open(pdfUrl, "_blank");
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header bar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b bg-muted/20 shrink-0">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <div className="size-6 rounded bg-primary/8 flex items-center justify-center shrink-0">
            <FileText className="size-3 text-primary/70" />
          </div>
          <span className="text-xs font-medium truncate">{filename}</span>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <Badge variant="outline" className="text-[10px] h-5 font-mono">
            {documentId}
          </Badge>
          <Button
            variant="ghost"
            size="icon"
            onClick={openInNewTab}
            className="size-6 text-muted-foreground hover:text-foreground"
            title="Open in new tab"
          >
            <ExternalLink className="size-3" />
          </Button>
        </div>
      </div>

      {/* PDF iframe */}
      <iframe
        src={pdfUrl}
        className="flex-1 w-full border-0"
        title="PDF Viewer"
      />
    </div>
  );
}
