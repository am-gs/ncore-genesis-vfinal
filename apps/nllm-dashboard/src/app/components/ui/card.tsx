     1	// Card component
     2	
     3	import * as React from "react"
     4	
     5	import { cn } from "@/app/lib/utils"
     6	
     7	const Card = React.forwardRef<
     8	  HTMLDivElement,
     9	  React.HTMLAttributes<HTMLDivElement>
    10	>(({ className, ...props }, ref) => (
    11	  <div
    12	    ref={ref}
    13	    className={cn(
    14	      "rounded-xl border border-line bg-panel text-text shadow",
    15	      className
    16	    )}
    17	    {...props}
    18	  />
    19	))
    20	Card.displayName = "Card"
    21	
    22	const CardHeader = React.forwardRef<
    23	  HTMLDivElement,
    24	  React.HTMLAttributes<HTMLDivElement>
    25	>(({ className, ...props }, ref) => (
    26	  <div
    27	    ref={ref}
    28	    className={cn("flex flex-col space-y-1.5 p-4", className)}
    29	    {...props}
    30	  />
    31	))
    32	CardHeader.displayName = "CardHeader"
    33	
    34	const CardTitle = React.forwardRef<
    35	  HTMLParagraphElement,
    36	  React.HTMLAttributes<HTMLHeadingElement>
    37	>(({ className, ...props }, ref) => (
    38	  <h3
    39	    ref={ref}
    40	    className={cn("font-semibold leading-none tracking-tight", className)}
    41	    {...props}
    42	  />
    43	))
    44	CardTitle.displayName = "CardTitle"
    45	
    46	const CardDescription = React.forwardRef<
    47	  HTMLParagraphElement,
    48	  React.HTMLAttributes<HTMLParagraphElement>
    49	>(({ className, ...props }, ref) => (
    50	  <p
    51	    ref={ref}
    52	    className={cn("text-sm text-text-secondary", className)}
    53	    {...props}
    54	  />
    55	))
    56	CardDescription.displayName = "CardDescription"
    57	
    58	const CardContent = React.forwardRef<
    59	  HTMLDivElement,
    60	  React.HTMLAttributes<HTMLDivElement>
    61	>(({ className, ...props }, ref) => (
    62	  <div ref={ref} className={cn("p-4 pt-0", className)} {...props} />
    63	))
    64	CardContent.displayName = "CardContent"
    65	
    66	const CardFooter = React.forwardRef<
    67	  HTMLDivElement,
    68	  React.HTMLAttributes<HTMLDivElement>
    69	>(({ className, ...props }, ref) => (
    70	  <div
    71	    ref={ref}
    72	    className={cn("flex items-center p-4 pt-0", className)}
    73	    {...props}
    74	  />
    75	))
    76	CardFooter.displayName = "CardFooter"
    77	
    78	export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }