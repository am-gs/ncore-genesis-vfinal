     1	// Input component
     2	
     3	import * as React from "react"
     4	
     5	import { cn } from "@/app/lib/utils"
     6	
     7	export interface InputProps
     8	  extends React.InputHTMLAttributes<HTMLInputElement> {}
     9	
    10	const Input = React.forwardRef<HTMLInputElement, InputProps>(
    11	  ({ className, type, ...props }, ref) => {
    12	    return (
    13	      <input
    14	        type={type}
    15	        className={cn(
    16	          "flex h-9 w-full rounded-md border border-line bg-transparent px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-text-secondary focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-accent disabled:cursor-not-allowed disabled:opacity-50",
    17	          className
    18	        )}
    19	        ref={ref}
    20	        {...props}
    21	      />
    22	    )
    23	  }
    24	)
    25	Input.displayName = "Input"
    26	
    27	export { Input }