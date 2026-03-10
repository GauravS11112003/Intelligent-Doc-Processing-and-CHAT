"use client";

import { useState } from "react";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { UploadZone } from "@/components/upload-zone";
import { PdfViewer } from "@/components/pdf-viewer";
import { ChatPanel } from "@/components/chat-panel";
import { ExtractPanel } from "@/components/extract-panel";
import {
  MessageSquare,
  TableProperties,
  ArrowLeft,
  FileText,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

export default function Home() {
  const [documentId, setDocumentId] = useState<string | null>(null);
  const [filename, setFilename] = useState("");
  const [activeTab, setActiveTab] = useState("chat");
  const [pdfCollapsed, setPdfCollapsed] = useState(false);

  const handleUploadSuccess = (docId: string, name: string) => {
    setDocumentId(docId);
    setFilename(name);
  };

  const handleReset = () => {
    setDocumentId(null);
    setFilename("");
    setActiveTab("chat");
    setPdfCollapsed(false);
  };

  if (!documentId) {
    return <UploadZone onUploadSuccess={handleUploadSuccess} />;
  }

  return (
    <div className="flex h-[calc(100vh-56px)] bg-muted/30">
      {/* Left: PDF Viewer - collapsible */}
      <div
        className={`border-r bg-background transition-all duration-300 ease-in-out flex flex-col ${
          pdfCollapsed ? "w-0 overflow-hidden border-r-0" : "w-[42%]"
        }`}
      >
        <PdfViewer documentId={documentId} filename={filename} />
      </div>

      {/* Right: Tools panel - expands when PDF is collapsed */}
      <div className={`flex flex-col transition-all duration-300 ease-in-out ${
        pdfCollapsed ? "w-full" : "w-[58%]"
      }`}>
        <Tabs value={activeTab} onValueChange={setActiveTab} className="flex flex-col h-full">
          {/* Tab header bar */}
          <div className="flex items-center justify-between border-b bg-background px-1.5 shrink-0">
            <div className="flex items-center">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setPdfCollapsed(!pdfCollapsed)}
                className="size-8 mr-1 text-muted-foreground hover:text-foreground"
                title={pdfCollapsed ? "Show PDF" : "Hide PDF"}
              >
                {pdfCollapsed ? (
                  <PanelLeftOpen className="size-4" />
                ) : (
                  <PanelLeftClose className="size-4" />
                )}
              </Button>

              <TabsList variant="line" className="h-11">
                <TabsTrigger value="chat" className="gap-1.5">
                  <MessageSquare className="size-3.5" />
                  <span className="font-medium">Chat</span>
                  <span className="ml-0.5 px-1.5 py-0.5 text-[10px] rounded-full bg-primary/10 text-primary font-semibold">
                    RAG
                  </span>
                </TabsTrigger>
                <TabsTrigger value="extract" className="gap-1.5">
                  <TableProperties className="size-3.5" />
                  <span className="font-medium">Extract</span>
                  <span className="ml-0.5 px-1.5 py-0.5 text-[10px] rounded-full bg-amber-500/10 text-amber-600 font-semibold">
                    IDP
                  </span>
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="flex items-center gap-1.5">
              <div className="hidden sm:flex items-center gap-1.5 mr-2 px-2 py-1 rounded-md bg-muted/50 text-[11px] text-muted-foreground">
                <FileText className="size-3" />
                <span className="max-w-[120px] truncate font-medium">{filename}</span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleReset}
                className="text-muted-foreground hover:text-foreground h-7 text-xs gap-1"
              >
                <ArrowLeft className="size-3" />
                New Doc
              </Button>
            </div>
          </div>

          {/* Tab content */}
          <TabsContent value="chat" className="mt-0 flex-1 overflow-hidden">
            <ChatPanel documentId={documentId} />
          </TabsContent>
          <TabsContent value="extract" className="mt-0 flex-1 overflow-hidden">
            <ExtractPanel documentId={documentId} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
