import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Search, ArrowLeft, Loader2 } from 'lucide-react'
import { apiListChats, apiListMessages, getMediaUrl, type ChatSummary, type MessageItem } from '@/lib/api'
import { PageHeader } from '@/components/layout/PageHeader'
import { Card, CardContent } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'

const APP_COLORS: Record<string, string> = {
  WhatsApp: 'text-green-400',
  Telegram: 'text-blue-400',
  Signal: 'text-purple-400',
  Messenger: 'text-blue-500',
  iMessage: 'text-blue-300',
  Phone: 'text-yellow-400',
}

function formatTs(ts: string | null): string {
  if (!ts) return '?'
  return new Date(ts).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function ChatList({
  chats,
  onSelect,
}: {
  chats: ChatSummary[]
  onSelect: (c: ChatSummary) => void
}) {
  const [filter, setFilter] = useState('')
  const visible = chats.filter(
    (c) =>
      !filter ||
      (c.chat_id ?? '').toLowerCase().includes(filter.toLowerCase()) ||
      (c.participant ?? '').toLowerCase().includes(filter.toLowerCase()) ||
      (c.app ?? '').toLowerCase().includes(filter.toLowerCase()),
  )

  return (
    <div className="space-y-3">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dim" />
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filtrar conversas..."
          style={{
            width: '100%',
            height: '2.75rem',
            borderRadius: '0.5rem',
            border: '1px solid #262626',
            backgroundColor: '#141414',
            paddingLeft: '2.5rem',
            paddingRight: '1rem',
            fontSize: '0.875rem',
            color: '#ededed',
          }}
        />
      </div>
      {visible.map((c) => (
        <Card
          key={`${c.app ?? ''}::${c.chat_id ?? 'null'}`}
          className="cursor-pointer hover:border-border-hover"
          onClick={() => onSelect(c)}
        >
          <CardContent className="flex items-center gap-4 py-3">
            <MessageSquare className={`h-5 w-5 shrink-0 ${APP_COLORS[c.app ?? ''] ?? 'text-muted'}`} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate font-medium text-sm text-foreground">
                  {c.participant ?? c.chat_id ?? '(sem ID)'}
                </span>
                {c.app && <Badge className="text-[10px] shrink-0">{c.app}</Badge>}
              </div>
              <p className="text-xs text-dim mt-0.5">
                {c.message_count} mensagens · {formatTs(c.first_ts)} → {formatTs(c.last_ts)}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function MessageBubble({ msg, caseId }: { msg: MessageItem; caseId: string }) {
  const isOut = msg.direction === 'outgoing'
  return (
    <div className={`flex ${isOut ? 'justify-end' : 'justify-start'} mb-2`}>
      <div
        style={{
          maxWidth: '75%',
          borderRadius: '0.75rem',
          padding: '0.5rem 0.75rem',
          backgroundColor: isOut ? '#2a2a2a' : '#1f1f1f',
          border: '1px solid',
          borderColor: isOut ? '#3f3f3f' : '#2a2a2a',
        }}
      >
        {msg.sender && !isOut && (
          <p className="text-[10px] text-blue-300 mb-1 font-medium truncate">{msg.sender}</p>
        )}
        {msg.text && <p className="text-sm text-foreground leading-relaxed">{msg.text}</p>}
        {msg.media_hash && (
          <div className="mt-2 overflow-hidden rounded" style={{ maxWidth: '200px' }}>
            <img
              src={getMediaUrl(msg.media_hash, caseId)}
              alt="mídia"
              className="w-full object-contain"
              style={{ maxHeight: '160px' }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
            />
          </div>
        )}
        <p className="text-[10px] text-dim mt-1 text-right">{formatTs(msg.ts)}</p>
      </div>
    </div>
  )
}

function MessageView({
  caseId,
  chat,
  onBack,
}: {
  caseId: string
  chat: ChatSummary
  onBack: () => void
}) {
  const [page, setPage] = useState(0)
  const limit = 50

  const { data, isLoading } = useQuery({
    queryKey: ['messages', caseId, chat.chat_id, page],
    queryFn: () =>
      apiListMessages(caseId, {
        app: chat.app ?? undefined,
        chatId: chat.chat_id ?? undefined,
        limit,
        offset: page * limit,
      }),
    enabled: !!caseId,
  })

  const msgs = data?.messages ?? []
  const total = data?.total ?? 0

  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <Button variant="secondary" size="sm" onClick={onBack} className="gap-1.5">
          <ArrowLeft className="h-3.5 w-3.5" />
          Conversas
        </Button>
        <div className="min-w-0">
          <p className="font-medium text-sm text-foreground truncate">
            {chat.participant ?? chat.chat_id ?? '(sem ID)'}
          </p>
          <p className="text-xs text-dim">{chat.app} · {total} mensagens</p>
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : msgs.length === 0 ? (
        <EmptyState icon={MessageSquare} title="Nenhuma mensagem" />
      ) : (
        <div className="space-y-0 px-2">
          {msgs.map((m) => (
            <MessageBubble key={`${m.chat_id ?? ''}::${m.id}`} msg={m} caseId={caseId} />
          ))}
        </div>
      )}

      {total > limit && (
        <div className="mt-4 flex items-center justify-center gap-3">
          <Button variant="secondary" size="sm" onClick={() => setPage(Math.max(0, page - 1))} disabled={page === 0}>
            Anterior
          </Button>
          <span className="text-xs text-dim">Página {page + 1} de {Math.ceil(total / limit)}</span>
          <Button variant="secondary" size="sm" onClick={() => setPage(page + 1)} disabled={(page + 1) * limit >= total}>
            Próxima
          </Button>
        </div>
      )}
    </>
  )
}

export function ConversasTab({ caseId }: { caseId: string }) {
  const [selectedChat, setSelectedChat] = useState<ChatSummary | null>(null)

  const { data: chats = [], isLoading } = useQuery({
    queryKey: ['chats', caseId],
    queryFn: () => apiListChats(caseId),
    enabled: !!caseId,
  })

  return (
    <>
      {!selectedChat && (
        <PageHeader
          icon={MessageSquare}
          title="Conversas"
          description={`${chats.length} conversa(s) · clique para abrir`}
        />
      )}

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-5 w-5 animate-spin text-muted" />
        </div>
      ) : selectedChat ? (
        <MessageView caseId={caseId} chat={selectedChat} onBack={() => setSelectedChat(null)} />
      ) : chats.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="Nenhuma conversa"
          description="As mensagens aparecem após a ingestão de UFDRs com apps de comunicação."
        />
      ) : (
        <ChatList chats={chats} onSelect={setSelectedChat} />
      )}
    </>
  )
}
