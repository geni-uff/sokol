import { cva, type VariantProps } from 'class-variance-authority'
import { Slot } from '@radix-ui/react-slot'
import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '@/lib/cn'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2.5 rounded-lg font-medium transition-colors duration-150 disabled:pointer-events-none disabled:opacity-40',
  {
    variants: {
      variant: {
        default: 'bg-foreground text-background hover:bg-foreground/90',
        secondary:
          'border border-border bg-transparent text-foreground hover:border-border-hover hover:bg-white/5',
        ghost: 'text-muted hover:text-foreground hover:bg-white/5',
        danger: 'bg-danger/10 text-danger hover:bg-danger/20 border border-danger/20',
      },
      size: {
        sm: 'h-9 min-h-9 px-4 py-2 text-sm',
        md: 'h-11 min-h-11 px-5 py-2.5 text-sm',
        lg: 'h-12 min-h-12 px-6 py-3 text-sm',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'md',
    },
  },
)

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size }), className)}
        ref={ref}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'
