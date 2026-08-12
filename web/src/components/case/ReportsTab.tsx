import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FileDown, Loader2, Plus, Calendar, Download } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { apiDownloadCaseExport, type BulkExportKind } from '@/lib/api'

interface Report {
  report_id: string
  case_id: string
  created_at: string
  status: string
  file_size: number
}

function authHeader(): Record<string, string> {
  const token = localStorage.getItem('sokol_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiGenerateReport(caseId: string, title: string): Promise<Report> {
  const response = await fetch(`/api/reports?case_id=${caseId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeader(),
    },
    body: JSON.stringify({ title }),
  })

  if (!response.ok) throw new Error('Failed to generate report')
  return response.json()
}

async function apiListReports(caseId: string): Promise<Report[]> {
  const response = await fetch(`/api/reports?case_id=${caseId}`, {
    headers: authHeader(),
  })

  if (!response.ok) throw new Error('Failed to fetch reports')
  return response.json()
}

async function downloadReport(caseId: string, reportId: string, format: 'html' | 'pdf') {
  const url = `/api/reports/${reportId}/download?case_id=${caseId}&format=${format}`
  const res = await fetch(url, { headers: authHeader() })
  if (!res.ok) throw new Error(`Download ${format} failed`)
  const blob = await res.blob()
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = `report-${reportId}.${format}`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(link.href)
}

const BULK_EXPORTS: { kind: BulkExportKind; label: string; hint: string }[] = [
  { kind: 'zip', label: 'ZIP do caso', hint: 'Pacote completo (JSON)' },
  { kind: 'timeline.csv', label: 'Timeline CSV', hint: 'Eventos em CSV' },
  { kind: 'contacts.vcf', label: 'Contatos VCF', hint: 'vCard 3.0' },
  { kind: 'contacts.csv', label: 'Contatos CSV', hint: 'Mesma base do VCF' },
  { kind: 'locations.kml', label: 'Localizações KML', hint: 'Google Earth' },
]

export function ReportsTab({ caseId }: { caseId: string }) {
  const [generating, setGenerating] = useState(false)
  const [exporting, setExporting] = useState<BulkExportKind | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: reports = [], isLoading } = useQuery({
    queryKey: ['reports', caseId],
    queryFn: () => apiListReports(caseId),
    enabled: !!caseId,
  })

  const generateMutation = useMutation({
    mutationFn: async () => {
      setGenerating(true)
      try {
        await apiGenerateReport(caseId, `Laudo — ${new Date().toLocaleString('pt-BR')}`)
        queryClient.invalidateQueries({ queryKey: ['reports', caseId] })
      } finally {
        setGenerating(false)
      }
    },
  })

  async function handleExport(kind: BulkExportKind) {
    setExportError(null)
    setExporting(kind)
    try {
      await apiDownloadCaseExport(caseId, kind)
    } catch (e) {
      setExportError(e instanceof Error ? e.message : 'Falha no export')
    } finally {
      setExporting(null)
    }
  }

  if (isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted" />
      </div>
    )
  }

  return (
    <>
      <PageHeader
        icon={FileDown}
        title="Relatórios"
        description={`${reports.length} relatório(s) gerado(s)`}
      />

      <div className="mb-8">
        <h2 className="mb-1 text-sm font-medium text-foreground">Export em massa</h2>
        <p className="mb-3 text-xs text-dim">
          Downloads auditados do caso (CSV, vCard, KML e ZIP).
        </p>
        <div className="flex flex-wrap gap-2">
          {BULK_EXPORTS.map(({ kind, label, hint }) => (
            <Button
              key={kind}
              variant="secondary"
              size="sm"
              disabled={exporting !== null}
              title={hint}
              onClick={() => void handleExport(kind)}
              className="flex items-center gap-2"
            >
              {exporting === kind ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Download className="h-3.5 w-3.5" />
              )}
              {label}
            </Button>
          ))}
        </div>
        {exportError && (
          <p className="mt-2 text-xs text-red-600" role="alert">
            {exportError}
          </p>
        )}
      </div>

      <div className="mb-6">
        <Button
          onClick={() => generateMutation.mutate()}
          disabled={generating || generateMutation.isPending}
          className="flex items-center gap-2"
        >
          {generating || generateMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Gerando...
            </>
          ) : (
            <>
              <Plus className="h-4 w-4" />
              Gerar Novo Relatório
            </>
          )}
        </Button>
      </div>

      {reports.length === 0 ? (
        <EmptyState
          icon={FileDown}
          title="Nenhum relatório"
          description="Clique em 'Gerar Novo Relatório' para criar um laudo forense"
        />
      ) : (
        <div className="space-y-3">
          {reports.map((report) => (
            <Card key={report.report_id} className="hover:border-border-hover">
              <CardContent className="flex items-center justify-between gap-3 py-4">
                <div className="flex min-w-0 flex-1 items-center gap-4">
                  <FileDown className="h-5 w-5 shrink-0 text-muted" />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-foreground">
                      Laudo investigativo
                    </p>
                    <div className="mt-1 flex items-center gap-3 text-xs text-dim">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {new Date(report.created_at).toLocaleString('pt-BR')}
                      </span>
                      <span className="capitalize">{report.status}</span>
                      {report.file_size > 0 && (
                        <span>{(report.file_size / 1024).toFixed(1)} KB</span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void downloadReport(caseId, report.report_id, 'html')}
                  >
                    HTML
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => void downloadReport(caseId, report.report_id, 'pdf')}
                  >
                    PDF
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </>
  )
}
