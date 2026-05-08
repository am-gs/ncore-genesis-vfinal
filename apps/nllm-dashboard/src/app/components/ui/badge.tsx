// Badge component

import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/app/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-md border border-line px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-accent text-text-inverse shadow hover:bg-accent/80",
        secondary:
          "border-transparent bg-panel-2 text-text hover:bg-panel-2/80",
        destructive:
          "border-transparent bg-bad text-text-inverse shadow hover:bg-bad/80",
        outline: "text-text",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
