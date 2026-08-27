import * as DialogPrimitive from '@radix-ui/react-dialog'
import { X } from 'lucide-react'
import { getMediaUrl } from '@/lib/api'

interface MediaLightboxProps {
  open: boolean
  onClose: () => void
  caseId: string
  hash: string | null
  mimeType?: string | null
}

export function MediaLightbox({
  open,
  onClose,
  caseId,
  hash,
  mimeType,
}: MediaLightboxProps) {
  const src = hash ? getMediaUrl(hash, caseId) : ''
  const isVideo = mimeType?.startsWith('video/') ?? false

  return (
    <DialogPrimitive.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose()
      }}
    >
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-[100] bg-black/85 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className="fixed left-1/2 top-1/2 z-[100] h-[calc(100vh-5rem)] w-[calc(100vw-5rem)] -translate-x-1/2 -translate-y-1/2 border-0 bg-transparent p-0 shadow-none outline-none"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          <DialogPrimitive.Title className="sr-only">
            Mídia expandida
          </DialogPrimitive.Title>
          <DialogPrimitive.Description className="sr-only">
            Esc ou clique fora para fechar
          </DialogPrimitive.Description>

          <DialogPrimitive.Close
            className="fixed right-6 top-6 z-[110] rounded-lg p-3 text-white/80 transition-colors hover:bg-white/10 hover:text-white md:right-10 md:top-10"
            aria-label="Fechar"
          >
            <X className="h-6 w-6" />
          </DialogPrimitive.Close>

          {hash &&
            (isVideo ? (
              <video
                src={src}
                controls
                className="h-full w-full object-contain"
              />
            ) : (
              <img
                src={src}
                alt={mimeType || 'imagem'}
                className="h-full w-full object-contain"
              />
            ))}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  )
}

export function isExpandableMedia(mimeType?: string | null): boolean {
  if (!mimeType) return true
  return (
    mimeType.startsWith('image/') ||
    mimeType.startsWith('video/') ||
    mimeType === 'application/octet-stream'
  )
}
