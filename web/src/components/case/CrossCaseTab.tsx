import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { apiCrossCase, apiListCases, type CrossCaseResult, type Case } from '@/lib/api'
import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { EmptyState } from '@/components/ui/EmptyState'
import { Loader2, Phone, Mail, MapPin, AlertTriangle, GitMerge } from 'lucide-react'

interface Props {
  caseId: string
}

export function CrossCaseTab({ caseId }: Props) {
  const [selectedIds, setSelectedIds] = useState<string[]>([caseId])
  const [justification, setJustification] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [result, setResult] = useState<CrossCaseResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { data: allCases = [] } = useQuery({
    queryKey: ['cases'],
    queryFn: apiListCases,
  })

  const otherCases = allCases.filter((c: { id: string }) => c.id !== caseId)

  function toggleCase(id: string) {
    setSelectedIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id],
    )
    setResult(null)
    setSubmitted(false)
    setError(null)
  }

  async function run() {
    if (!justification.trim()) return
    if (selectedIds.length < 2) {
      setError('Selecione ao menos 1 outro caso para comparar.')
      return
    }
    setLoading(true)
    setError(null)
    try {
      const res = await apiCrossCase(selectedIds, justification)
      setResult(res)
      setSubmitted(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '24px', maxWidth: '860px', margin: '0 auto' }}>
      <div style={{ marginBottom: '20px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
          Análise Cruzada
        </h2>
        <p style={{ fontSize: '13px', color: '#94a3b8' }}>
          Identifica telefones, e-mails e locais compartilhados entre casos.
          Requer papel <strong>Admin</strong> em todos os casos selecionados.
        </p>
      </div>

      {/* Indicator warning */}
      <div style={{
        background: 'rgba(234,179,8,0.1)',
        border: '1px solid rgba(234,179,8,0.3)',
        borderRadius: '8px',
        padding: '10px 14px',
        marginBottom: '20px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '8px',
      }}>
        <AlertTriangle size={15} style={{ color: '#eab308', marginTop: '2px', flexShrink: 0 }} />
        <span style={{ fontSize: '12px', color: '#fde68a', lineHeight: '1.5' }}>
          Resultados são <strong>indícios automáticos</strong>, não fatos confirmados.
          Valide manualmente antes de incluir em laudo.
        </span>
      </div>

      {/* Case selector */}
      <Card style={{ marginBottom: '16px' }}>
        <CardContent style={{ padding: '16px' }}>
          <p style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '10px', fontWeight: 500 }}>
            Casos a comparar (este caso já está incluído):
          </p>
          {otherCases.length === 0 ? (
            <p style={{ fontSize: '13px', color: '#64748b' }}>Nenhum outro caso disponível.</p>
          ) : (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {(otherCases as Case[]).map((c) => {
                const selected = selectedIds.includes(c.id)
                return (
                  <button
                    key={c.id}
                    onClick={() => toggleCase(c.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: selected ? '1px solid #3b82f6' : '1px solid #334155',
                      background: selected ? 'rgba(59,130,246,0.15)' : 'rgba(30,41,59,0.5)',
                      color: selected ? '#93c5fd' : '#94a3b8',
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    {c.name}
                  </button>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Justification */}
      <Card style={{ marginBottom: '16px' }}>
        <CardContent style={{ padding: '16px' }}>
          <label style={{ fontSize: '12px', color: '#94a3b8', fontWeight: 500, display: 'block', marginBottom: '8px' }}>
            Justificativa (obrigatória) *
          </label>
          <textarea
            value={justification}
            onChange={e => setJustification(e.target.value)}
            placeholder="Ex.: Investigação de quadrilha com possíveis conexões entre os casos PA7 e PA10..."
            rows={3}
            style={{
              width: '100%',
              background: 'rgba(15,23,42,0.6)',
              border: '1px solid #334155',
              borderRadius: '6px',
              color: '#e2e8f0',
              padding: '10px',
              fontSize: '13px',
              resize: 'vertical',
              boxSizing: 'border-box',
            }}
          />
        </CardContent>
      </Card>

      {error && (
        <p style={{ color: '#f87171', fontSize: '13px', marginBottom: '12px' }}>{error}</p>
      )}

      <Button
        onClick={run}
        disabled={loading || !justification.trim() || selectedIds.length < 2}
        style={{ marginBottom: '24px' }}
      >
        {loading ? <Loader2 size={14} className="animate-spin" style={{ marginRight: '6px' }} /> : <GitMerge size={14} style={{ marginRight: '6px' }} />}
        {loading ? 'Analisando...' : 'Comparar casos'}
      </Button>

      {/* Results */}
      {submitted && result && (
        <div>
          {/* Score */}
          <div style={{ marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '13px', color: '#94a3b8' }}>Similaridade:</span>
            <span style={{
              fontSize: '20px',
              fontWeight: 700,
              color: result.similarity_score > 0.3 ? '#f87171' : result.similarity_score > 0 ? '#fbbf24' : '#64748b',
            }}>
              {(result.similarity_score * 100).toFixed(1)}%
            </span>
            <Badge variant={result.similarity_score > 0 ? 'warning' : 'default'}>Indicator</Badge>
          </div>

          <SelectorSection
            icon={<Phone size={14} />}
            title="Telefones compartilhados"
            items={result.shared_phones}
            caseIds={result.case_ids}
          />
          <SelectorSection
            icon={<Mail size={14} />}
            title="E-mails compartilhados"
            items={result.shared_emails}
            caseIds={result.case_ids}
          />
          <LocationSection items={result.shared_locations} />

          {result.shared_phones.length === 0 &&
            result.shared_emails.length === 0 &&
            result.shared_locations.length === 0 && (
              <EmptyState
                title="Sem correspondências"
                description="Nenhum telefone, e-mail ou local compartilhado encontrado entre os casos selecionados."
              />
            )}
        </div>
      )}
    </div>
  )
}

function SelectorSection({
  icon,
  title,
  items,
  caseIds,
}: {
  icon: React.ReactNode
  title: string
  items: { value: string; cases: Record<string, number>; confidence: number }[]
  caseIds: string[]
}) {
  if (items.length === 0) return null
  return (
    <Card style={{ marginBottom: '16px' }}>
      <CardContent style={{ padding: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <span style={{ color: '#60a5fa' }}>{icon}</span>
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#e2e8f0' }}>{title}</span>
          <Badge>{items.length}</Badge>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {items.map(item => (
            <div
              key={item.value}
              style={{
                background: 'rgba(15,23,42,0.5)',
                borderRadius: '6px',
                padding: '10px 12px',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <span style={{ fontSize: '13px', color: '#e2e8f0', fontFamily: 'monospace' }}>
                {item.value}
              </span>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                {Object.entries(item.cases).map(([cid, cnt]) => (
                  <span
                    key={cid}
                    style={{
                      fontSize: '11px',
                      color: '#94a3b8',
                      background: 'rgba(51,65,85,0.7)',
                      padding: '2px 7px',
                      borderRadius: '4px',
                    }}
                  >
                    {cid.slice(0, 8)}… ×{cnt}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

function LocationSection({
  items,
}: {
  items: {
    case_id_a: string
    case_id_b: string
    ts_a: string | null
    ts_b: string | null
    distance_m: number
  }[]
}) {
  if (items.length === 0) return null
  return (
    <Card style={{ marginBottom: '16px' }}>
      <CardContent style={{ padding: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <MapPin size={14} style={{ color: '#34d399' }} />
          <span style={{ fontSize: '14px', fontWeight: 600, color: '#e2e8f0' }}>
            Locais próximos (&lt;500m)
          </span>
          <Badge>{items.length}</Badge>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {items.map((item, i) => (
            <div
              key={i}
              style={{
                background: 'rgba(15,23,42,0.5)',
                borderRadius: '6px',
                padding: '10px 12px',
                fontSize: '12px',
                color: '#94a3b8',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span>
                  Caso <code>{item.case_id_a.slice(0, 8)}…</code>
                  {' '}↔{' '}
                  Caso <code>{item.case_id_b.slice(0, 8)}…</code>
                </span>
                <span style={{ color: '#34d399', fontWeight: 600 }}>
                  {item.distance_m.toFixed(0)} m
                </span>
              </div>
              {(item.ts_a || item.ts_b) && (
                <div style={{ color: '#64748b' }}>
                  {item.ts_a && <span>A: {new Date(item.ts_a).toLocaleString('pt-BR')}</span>}
                  {item.ts_a && item.ts_b && ' · '}
                  {item.ts_b && <span>B: {new Date(item.ts_b).toLocaleString('pt-BR')}</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
