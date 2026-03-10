"use client";

import { useState } from "react";
import {
  Plus,
  Trash2,
  Play,
  Loader2,
  CheckCircle2,
  Check,
  FileJson,
  FileSpreadsheet,
  RotateCcw,
  Sparkles,
  Receipt,
  FileText,
  Briefcase,
  GraduationCap,
  Building2,
  Stethoscope,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Clipboard,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

const API_URL = "http://localhost:8000";

interface SchemaField {
  id: string;
  field_name: string;
  data_type: string;
  description: string;
  required: boolean;
}

interface ExtractPanelProps {
  documentId: string;
}

interface SchemaTemplate {
  name: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
  color: string;
  fields: Omit<SchemaField, "id">[];
}

const SCHEMA_TEMPLATES: SchemaTemplate[] = [
  {
    name: "Invoice",
    icon: Receipt,
    description: "Extract invoice details",
    color: "text-blue-600 bg-blue-500/10",
    fields: [
      { field_name: "invoice_number", data_type: "Text", description: "The invoice number or ID", required: true },
      { field_name: "invoice_date", data_type: "Date", description: "Date the invoice was issued", required: true },
      { field_name: "due_date", data_type: "Date", description: "Payment due date", required: false },
      { field_name: "vendor_name", data_type: "Text", description: "Name of the vendor or supplier", required: true },
      { field_name: "total_amount", data_type: "Number", description: "Total amount due", required: true },
      { field_name: "currency", data_type: "Text", description: "Currency of the amounts (e.g. USD, EUR)", required: false },
      { field_name: "line_items", data_type: "List", description: "List of line items/products on the invoice", required: false },
      { field_name: "tax_amount", data_type: "Number", description: "Total tax amount", required: false },
    ],
  },
  {
    name: "Contract",
    icon: Briefcase,
    description: "Extract contract information",
    color: "text-purple-600 bg-purple-500/10",
    fields: [
      { field_name: "contract_title", data_type: "Text", description: "Title or name of the contract", required: true },
      { field_name: "parties", data_type: "List", description: "Names of all parties involved", required: true },
      { field_name: "effective_date", data_type: "Date", description: "When the contract becomes effective", required: true },
      { field_name: "expiration_date", data_type: "Date", description: "When the contract expires", required: false },
      { field_name: "contract_value", data_type: "Number", description: "Total monetary value of the contract", required: false },
      { field_name: "key_terms", data_type: "List", description: "Key terms and conditions", required: false },
      { field_name: "governing_law", data_type: "Text", description: "Jurisdiction or governing law", required: false },
    ],
  },
  {
    name: "Resume / CV",
    icon: GraduationCap,
    description: "Extract candidate info",
    color: "text-emerald-600 bg-emerald-500/10",
    fields: [
      { field_name: "full_name", data_type: "Text", description: "Candidate's full name", required: true },
      { field_name: "email", data_type: "Text", description: "Email address", required: true },
      { field_name: "phone", data_type: "Text", description: "Phone number", required: false },
      { field_name: "skills", data_type: "List", description: "List of technical and professional skills", required: true },
      { field_name: "experience_years", data_type: "Number", description: "Total years of experience", required: false },
      { field_name: "education", data_type: "List", description: "Educational qualifications and degrees", required: false },
      { field_name: "work_history", data_type: "List", description: "Previous job titles and companies", required: false },
      { field_name: "summary", data_type: "Text", description: "Professional summary or objective", required: false },
    ],
  },
  {
    name: "Report",
    icon: FileText,
    description: "Extract report metadata",
    color: "text-orange-600 bg-orange-500/10",
    fields: [
      { field_name: "title", data_type: "Text", description: "Report title", required: true },
      { field_name: "author", data_type: "Text", description: "Author or organization name", required: true },
      { field_name: "date", data_type: "Date", description: "Publication or report date", required: true },
      { field_name: "summary", data_type: "Text", description: "Executive summary or abstract", required: true },
      { field_name: "key_findings", data_type: "List", description: "Main findings or conclusions", required: false },
      { field_name: "recommendations", data_type: "List", description: "Recommendations mentioned", required: false },
    ],
  },
  {
    name: "Real Estate",
    icon: Building2,
    description: "Property documents",
    color: "text-amber-600 bg-amber-500/10",
    fields: [
      { field_name: "property_address", data_type: "Text", description: "Full property address", required: true },
      { field_name: "owner_name", data_type: "Text", description: "Property owner name", required: true },
      { field_name: "property_type", data_type: "Text", description: "Type of property (residential, commercial, etc.)", required: false },
      { field_name: "sale_price", data_type: "Number", description: "Sale or listed price", required: false },
      { field_name: "square_footage", data_type: "Number", description: "Total area in square feet", required: false },
      { field_name: "date_listed", data_type: "Date", description: "Date property was listed or sold", required: false },
    ],
  },
  {
    name: "Medical",
    icon: Stethoscope,
    description: "Medical document extraction",
    color: "text-red-600 bg-red-500/10",
    fields: [
      { field_name: "patient_name", data_type: "Text", description: "Patient's full name", required: true },
      { field_name: "date_of_visit", data_type: "Date", description: "Date of the medical visit", required: true },
      { field_name: "diagnosis", data_type: "List", description: "Diagnoses or conditions", required: true },
      { field_name: "medications", data_type: "List", description: "Prescribed medications", required: false },
      { field_name: "doctor_name", data_type: "Text", description: "Attending physician name", required: false },
      { field_name: "follow_up_date", data_type: "Date", description: "Next follow-up appointment", required: false },
    ],
  },
];

const DATA_TYPES = [
  { value: "Text", label: "Text", color: "bg-slate-100 text-slate-700" },
  { value: "Number", label: "Number", color: "bg-blue-100 text-blue-700" },
  { value: "Date", label: "Date", color: "bg-green-100 text-green-700" },
  { value: "List", label: "List", color: "bg-purple-100 text-purple-700" },
  { value: "Boolean", label: "Boolean", color: "bg-amber-100 text-amber-700" },
  { value: "Currency", label: "Currency", color: "bg-emerald-100 text-emerald-700" },
];

export function ExtractPanel({ documentId }: ExtractPanelProps) {
  const [fields, setFields] = useState<SchemaField[]>([
    { id: "1", field_name: "", data_type: "Text", description: "", required: false },
  ]);
  const [results, setResults] = useState<Record<string, unknown> | null>(null);
  const [extractSources, setExtractSources] = useState<string[]>([]);
  const [isExtracting, setIsExtracting] = useState(false);
  const [isCloud, setIsCloud] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showTemplates, setShowTemplates] = useState(true);
  const [activeTemplate, setActiveTemplate] = useState<string | null>(null);

  const addField = () => {
    setFields((prev) => [
      ...prev,
      {
        id: String(Date.now()),
        field_name: "",
        data_type: "Text",
        description: "",
        required: false,
      },
    ]);
  };

  const removeField = (id: string) => {
    if (fields.length > 1) {
      setFields((prev) => prev.filter((f) => f.id !== id));
    }
  };

  const updateField = (id: string, key: keyof SchemaField, value: string | boolean) => {
    setFields((prev) =>
      prev.map((f) => (f.id === id ? { ...f, [key]: value } : f))
    );
  };

  const moveField = (index: number, direction: "up" | "down") => {
    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= fields.length) return;
    const newFields = [...fields];
    [newFields[index], newFields[newIndex]] = [newFields[newIndex], newFields[index]];
    setFields(newFields);
  };

  const applyTemplate = (template: SchemaTemplate) => {
    const newFields = template.fields.map((f, i) => ({
      ...f,
      id: String(Date.now() + i),
    }));
    setFields(newFields);
    setActiveTemplate(template.name);
    setShowTemplates(false);
    setResults(null);
    setError(null);
  };

  const resetSchema = () => {
    setFields([
      { id: String(Date.now()), field_name: "", data_type: "Text", description: "", required: false },
    ]);
    setResults(null);
    setExtractSources([]);
    setError(null);
    setActiveTemplate(null);
    setShowTemplates(true);
  };

  const runExtraction = async () => {
    const validFields = fields.filter((f) => f.field_name.trim());
    if (validFields.length === 0) {
      setError("Please define at least one field with a name.");
      return;
    }

    setIsExtracting(true);
    setError(null);
    setResults(null);

    try {
      const mappedType = (dt: string) => {
        if (dt === "Boolean") return "Text";
        if (dt === "Currency") return "Number";
        return dt;
      };

      const res = await fetch(`${API_URL}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          document_id: documentId,
          schema_fields: validFields.map((f) => ({
            field_name: f.field_name,
            data_type: mappedType(f.data_type),
            description: f.description + (f.data_type === "Boolean" ? " (answer true or false)" : "") + (f.data_type === "Currency" ? " (monetary amount as number)" : ""),
          })),
          model_choice: isCloud ? "cloud" : "local",
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Extraction failed");
      }

      const data = await res.json();
      setResults(data.data);
      setExtractSources(data.sources ?? []);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Extraction failed";
      setError(message);
    } finally {
      setIsExtracting(false);
    }
  };

  const downloadJSON = () => {
    if (!results) return;
    const blob = new Blob([JSON.stringify(results, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `extracted_${documentId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadCSV = () => {
    if (!results) return;
    const headers = Object.keys(results);
    const values = Object.values(results).map((v) =>
      Array.isArray(v) ? `"${v.join("; ")}"` : `"${String(v ?? "")}"`
    );
    const csv = headers.join(",") + "\n" + values.join(",");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `extracted_${documentId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const copyResults = async () => {
    if (!results) return;
    await navigator.clipboard.writeText(JSON.stringify(results, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filledFields = fields.filter((f) => f.field_name.trim()).length;

  return (
    <div className="flex flex-col h-full overflow-y-auto custom-scrollbar bg-gradient-to-b from-background to-muted/20">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b bg-background/80 backdrop-blur-sm shrink-0">
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
            isCloud
              ? "bg-blue-500/10 text-blue-600"
              : "bg-purple-500/10 text-purple-600"
          }`}>
            <Sparkles className="size-3" />
            {isCloud ? "Gemini 2.0 Flash" : "Qwen 2.5"}
          </div>
          {activeTemplate && (
            <Badge variant="secondary" className="text-[10px] h-5 gap-1">
              {activeTemplate}
            </Badge>
          )}
        </div>

          <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={resetSchema}
            className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1"
          >
            <RotateCcw className="size-3" />
            Reset
          </Button>
          <div className="flex items-center gap-2 pl-3 border-l">
            <Label className={`text-[11px] font-medium cursor-pointer transition-colors ${!isCloud ? "text-purple-600" : "text-muted-foreground"}`}>
              Local
            </Label>
            <Switch checked={isCloud} onCheckedChange={setIsCloud} className="scale-90" />
            <Label className={`text-[11px] font-medium cursor-pointer transition-colors ${isCloud ? "text-blue-600" : "text-muted-foreground"}`}>
              Cloud
            </Label>
          </div>
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* Template picker */}
        {showTemplates && !results && (
          <div className="animate-fade-in">
            <div className="flex items-center justify-between mb-2.5">
              <div>
                <h3 className="text-sm font-semibold">Quick Start Templates</h3>
                <p className="text-[11px] text-muted-foreground">
                  Choose a template or build your own schema below
                </p>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowTemplates(false)}
                className="h-6 text-[11px] text-muted-foreground"
              >
                Hide
              </Button>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {SCHEMA_TEMPLATES.map((template) => (
                <button
                  key={template.name}
                  onClick={() => applyTemplate(template)}
                  className="flex flex-col items-center gap-1.5 p-3 rounded-xl border bg-background hover:bg-accent hover:border-primary/20 transition-all duration-200 group text-center"
                >
                  <div className={`size-8 rounded-lg ${template.color} flex items-center justify-center group-hover:scale-110 transition-transform`}>
                    <template.icon className="size-4" />
                  </div>
                  <span className="text-xs font-medium">{template.name}</span>
                  <span className="text-[10px] text-muted-foreground leading-tight">
                    {template.description}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}

        {!showTemplates && !results && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowTemplates(true)}
            className="h-7 text-xs text-muted-foreground hover:text-foreground gap-1 -mt-1"
          >
            <ChevronDown className="size-3" />
            Show Templates
          </Button>
        )}

        {/* Schema builder heading */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Schema Builder</h3>
            <Badge variant="outline" className="text-[10px] h-5 font-normal">
              {filledFields} / {fields.length} fields
            </Badge>
          </div>
        </div>

        {/* Schema table */}
        <div className="rounded-xl border overflow-hidden bg-background shadow-sm">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/40 hover:bg-muted/40">
                <TableHead className="w-[32px] text-[11px]" />
                <TableHead className="w-[170px] text-[11px] font-semibold">Field Name</TableHead>
                <TableHead className="w-[120px] text-[11px] font-semibold">Type</TableHead>
                <TableHead className="text-[11px] font-semibold">Description</TableHead>
                <TableHead className="w-[60px] text-[11px] font-semibold text-center">Req.</TableHead>
                <TableHead className="w-[70px]" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {fields.map((field, index) => (
                <TableRow key={field.id} className="group">
                  <TableCell className="py-1.5 px-1">
                    <div className="flex flex-col gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => moveField(index, "up")}
                        disabled={index === 0}
                        className="p-0.5 rounded hover:bg-muted disabled:opacity-30"
                      >
                        <ChevronUp className="size-3 text-muted-foreground" />
                      </button>
                      <button
                        onClick={() => moveField(index, "down")}
                        disabled={index === fields.length - 1}
                        className="p-0.5 rounded hover:bg-muted disabled:opacity-30"
                      >
                        <ChevronDown className="size-3 text-muted-foreground" />
                      </button>
                    </div>
                  </TableCell>
                  <TableCell className="py-1.5">
                    <Input
                      value={field.field_name}
                      onChange={(e) =>
                        updateField(field.id, "field_name", e.target.value)
                      }
                      placeholder="e.g. invoice_number"
                      className="h-8 text-xs font-mono"
                    />
                  </TableCell>
                  <TableCell className="py-1.5">
                    <Select
                      value={field.data_type}
                      onValueChange={(v) =>
                        updateField(field.id, "data_type", v)
                      }
                    >
                      <SelectTrigger className="h-8 text-xs w-full">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DATA_TYPES.map((dt) => (
                          <SelectItem key={dt.value} value={dt.value}>
                            <div className="flex items-center gap-2">
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${dt.color}`}>
                                {dt.label}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell className="py-1.5">
                    <Input
                      value={field.description}
                      onChange={(e) =>
                        updateField(field.id, "description", e.target.value)
                      }
                      placeholder="What to extract..."
                      className="h-8 text-xs"
                    />
                  </TableCell>
                  <TableCell className="py-1.5 text-center">
                    <input
                      type="checkbox"
                      checked={field.required}
                      onChange={(e) =>
                        updateField(field.id, "required", e.target.checked)
                      }
                      className="size-3.5 rounded border-border accent-primary cursor-pointer"
                    />
                  </TableCell>
                  <TableCell className="py-1.5">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => removeField(field.id)}
                      disabled={fields.length === 1}
                      className="size-7 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={addField} className="h-8 text-xs gap-1.5">
            <Plus className="size-3" />
            Add Field
          </Button>
          <div className="flex-1" />
          <Button
            size="sm"
            onClick={runExtraction}
            disabled={isExtracting || filledFields === 0}
            className="h-8 text-xs gap-1.5 px-4 bg-gradient-to-r from-primary to-primary/80 hover:from-primary/90 hover:to-primary/70 shadow-sm"
          >
            {isExtracting ? (
              <Loader2 className="size-3 animate-spin" />
            ) : (
              <Play className="size-3" />
            )}
            {isExtracting ? "Extracting..." : "Run Extraction"}
          </Button>
        </div>

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-destructive/5 border border-destructive/20 text-destructive rounded-xl text-xs font-medium animate-fade-in">
            <AlertTriangle className="size-3.5 shrink-0" />
            {error}
          </div>
        )}

        {/* Results */}
        {results && (
          <div className="animate-fade-in-up space-y-3">
            <Separator />

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="size-6 rounded-full bg-emerald-500/10 flex items-center justify-center">
                  <CheckCircle2 className="size-3.5 text-emerald-600" />
                </div>
                <h3 className="text-sm font-semibold">Extracted Data</h3>
                <Badge variant="secondary" className="text-[10px] h-5">
                  {Object.keys(results).length} fields
                </Badge>
                {extractSources.length > 0 && (
                  <div className="flex items-center gap-1 ml-1">
                    {extractSources.map((s, i) => (
                      <Badge key={i} variant="outline" className="text-[9px] h-4 px-1.5 text-primary/70 border-primary/20">
                        {s}
                      </Badge>
                    ))}
                  </div>
                )}
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={copyResults}
                  className="h-7 text-[11px] gap-1"
                >
                  {copied ? (
                    <Check className="size-3 text-emerald-500" />
                  ) : (
                    <Clipboard className="size-3" />
                  )}
                  {copied ? "Copied" : "Copy"}
                </Button>
                <Button variant="ghost" size="sm" onClick={downloadJSON} className="h-7 text-[11px] gap-1">
                  <FileJson className="size-3" />
                  JSON
                </Button>
                <Button variant="ghost" size="sm" onClick={downloadCSV} className="h-7 text-[11px] gap-1">
                  <FileSpreadsheet className="size-3" />
                  CSV
                </Button>
              </div>
            </div>

            <div className="rounded-xl border overflow-hidden bg-background shadow-sm">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableHead className="w-[200px] text-[11px] font-semibold">Field</TableHead>
                    <TableHead className="text-[11px] font-semibold">Value</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Object.entries(results).map(([key, value]) => (
                    <TableRow key={key} className="hover:bg-muted/20">
                      <TableCell className="font-mono text-xs font-medium text-primary/80">
                        {key}
                      </TableCell>
                      <TableCell className="text-xs">
                        {Array.isArray(value) ? (
                          <div className="flex flex-wrap gap-1">
                            {(value as string[]).map((item, i) => (
                              <Badge
                                key={i}
                                variant="secondary"
                                className="text-[10px] font-normal"
                              >
                                {item}
                              </Badge>
                            ))}
                          </div>
                        ) : value === null || value === undefined ? (
                          <span className="text-muted-foreground italic">Not found</span>
                        ) : (
                          <span className="font-medium">{String(value)}</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            {/* Raw JSON preview */}
            <details className="group">
              <summary className="text-[11px] text-muted-foreground cursor-pointer hover:text-foreground transition-colors flex items-center gap-1">
                <ChevronDown className="size-3 group-open:rotate-180 transition-transform" />
                View raw JSON
              </summary>
              <pre className="mt-2 p-3 bg-muted/50 rounded-lg text-[11px] font-mono overflow-x-auto leading-relaxed">
                {JSON.stringify(results, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
