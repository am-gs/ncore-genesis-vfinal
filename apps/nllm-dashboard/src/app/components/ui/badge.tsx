     1	// Badge component
     2	
     3	import * as React from "react"
     4	import { cva, type VariantProps } from "class-variance-authority"
     5	
     6	import { cn } from "@/app/lib/utils"
     7	
     8	const badgeVariants = cva(
     9	  "inline-flex items-center rounded-md border border-line px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
    10	  {
    11	    variants: {
    12	      variant: {
    13	        default:
    14	          "border-transparent bg-accent text-text-inverse shadow hover:bg-accent/80",
    15	        secondary:
    16	          "border-transparent bg-panel-2 text-text hover:bg-panel-2/80",
    17	        destructive:
    18	          "border-transparent bg-bad text-text-inverse shadow hover:bg-bad/80",
    19	        outline: "text-text",
    20	      },
    21	    },
    22	    defaultVariants: {
    23	      variant: "default",
    24	    },
    25	  }
    26	)
    27	
    28	export interface BadgeProps
    29	  extends React.HTMLAttributes<HTMLDivElement>,
    30	    VariantProps<typeof badgeVariants> {}
    31	
    32	function Badge({ className, variant, ...props }: BadgeProps) {
    33	  return (
    34	    <div className={cn(badgeVariants({ variant }), className)} {...props} />
    35	  )
    36	}
    37	
    38	export { Badge, badgeVariants }