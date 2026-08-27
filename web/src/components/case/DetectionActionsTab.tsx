import { Card, CardContent } from '@/components/ui/Card'
import { Button } from '@/components/ui/Button'
import { useState } from 'react'
import { CheckCircle, Trash2, Tag, Share2 } from 'lucide-react'

interface DetectionItemProps {
  id: string
  thumbnail?: string
  title: string
  metadata: Record<string, any>
  onConfirm?: (id: string) => void
  onLabel?: (id: string, label: string) => void
  onDelete?: (id: string) => void
  onShare?: (id: string) => void
}

export function DetectionActionItem({
  id,
  thumbnail,
  title,
  metadata,
  onConfirm,
  onLabel,
  onDelete,
}: DetectionItemProps) {
  const [isConfirmed, setIsConfirmed] = useState(false)
  const [label, setLabel] = useState('')

  const handleConfirm = () => {
    setIsConfirmed(true)
    onConfirm?.(id)
  }

  const handleLabel = () => {
    if (label.trim()) {
      onLabel?.(id, label)
      setLabel('')
    }
  }

  return (
    <Card className="border-border">
      <CardContent className="py-4">
        <div className="flex items-start gap-4">
          {thumbnail && (
            <img
              src={thumbnail}
              alt={title}
              className="h-16 w-16 rounded-lg object-cover bg-surface-elevated"
            />
          )}

          <div className="flex-1">
            <h3 className="font-medium text-sm mb-2">{title}</h3>

            <div className="flex flex-wrap gap-2 mb-3">
              {Object.entries(metadata).map(([key, value]) => (
                <div key={key} className="text-xs bg-surface-elevated px-2 py-1 rounded">
                  <span className="text-dim">{key}:</span> {String(value)}
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant={isConfirmed ? 'secondary' : 'default'}
                onClick={handleConfirm}
                disabled={isConfirmed}
                className="flex items-center gap-1"
              >
                <CheckCircle className="h-3 w-3" />
                {isConfirmed ? 'Confirmado' : 'Confirmar'}
              </Button>

              <div className="flex items-center gap-1">
                <input
                  type="text"
                  placeholder="Label..."
                  value={label}
                  onChange={(e) => setLabel(e.target.value)}
                  style={{
                    height: '24px',
                    borderRadius: '4px',
                    border: '1px solid #262626',
                    backgroundColor: '#141414',
                    paddingLeft: '6px',
                    paddingRight: '6px',
                    fontSize: '12px',
                    color: '#ededed',
                  }}
                />
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={handleLabel}
                  className="flex items-center gap-1"
                >
                  <Tag className="h-3 w-3" />
                  Marcar
                </Button>
              </div>

              <Button
                size="sm"
                variant="secondary"
                onClick={() => onDelete?.(id)}
                className="flex items-center gap-1"
              >
                <Trash2 className="h-3 w-3" />
                Falso Positivo
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
