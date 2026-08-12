import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { FileDown, Loader2, Plus, Calendar } from 'lucide-react'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'

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

export function ReportsTab({ caseId }: { caseId: string }) {
  const [generating, setGenerating] = useState(false)
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
