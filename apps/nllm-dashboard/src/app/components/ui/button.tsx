     1	// Button component
     2	
     3	import * as React from "react"
     4	import { Slot } from "@radix-ui/react-slot"
     5	import { cva, type VariantProps } from "class-variance-authority"
     6	
     7	import { cn } from "@/app/lib/utils"
     8	
     9	const buttonVariants = cva(
    10	  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
    11	  {
    12	    variants: {
    13	      variant: {
    14	        default:
    15	          "bg-accent text-text-inverse shadow hover:bg-accent-2",
    16	        destructive:
    17	          "bg-bad text-text-inverse shadow-sm hover:bg-bad/90",
    18	        outline:
    19	          "border border-line bg-transparent shadow-sm hover:bg-panel-2 hover:text-text",
    20	        secondary:
    21	          "bg-panel-2 text-text shadow-sm hover:bg-panel-2/80",
    22	        ghost: "hover:bg-panel-2 hover:text-text",
    23	        link: "text-accent underline-offset-4 hover:underline",
    24	      },
    25	      size: {
    26	        default: "h-9 px-4 py-2",
    27	        sm: "h-8 rounded-md px-3 text-xs",
    28	        lg: "h-10 rounded-md px-8",
    29	        icon: "h-9 w-9",
    30	      },
    31	    },
    32	    defaultVariants: {
    33	      variant: "default",
    34	      size: "default",
    35	    },
    36	  }
    37	)
    38	
    39	export interface ButtonProps
    40	  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    41	    VariantProps<typeof buttonVariants> {
    42	  asChild?: boolean
    43	}
    44	
    45	const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
    46	  ({ className, variant, size, asChild = false, ...props }, ref) => {
    47	    const Comp = asChild ? Slot : "button"
    48	    return (
    49	      <Comp
    50	        className={cn(buttonVariants({ variant, size, className }))}
    51	        ref={ref}
    52	        {...props}
    53	      />
    54	    )
    55	  }
    56	)
    57	Button.displayName = "Button"
    58	
    59	export { Button, buttonVariants }