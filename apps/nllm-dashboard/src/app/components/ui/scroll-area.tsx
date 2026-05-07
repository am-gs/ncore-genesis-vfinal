     1	// ScrollArea component
     2	
     3	import * as React from "react"
     4	import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area"
     5	
     6	import { cn } from "@/app/lib/utils"
     7	
     8	const ScrollArea = React.forwardRef<
     9	  React.ElementRef<typeof ScrollAreaPrimitive.Root>,
    10	  React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.Root>
    11	>(({ className, children, ...props }, ref) => (
    12	  <ScrollAreaPrimitive.Root
    13	    ref={ref}
    14	    className={cn("relative overflow-hidden", className)}
    15	    {...props}
    16	  >
    17	    <ScrollAreaPrimitive.Viewport className="h-full w-full rounded-[inherit]">
    18	      {children}
    19	    </ScrollAreaPrimitive.Viewport>
    20	    <ScrollBar />
    21	    <ScrollAreaPrimitive.Corner />
    22	  </ScrollAreaPrimitive.Root>
    23	))
    24	ScrollArea.displayName = ScrollAreaPrimitive.Root.displayName
    25	
    26	const ScrollBar = React.forwardRef<
    27	  React.ElementRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>,
    28	  React.ComponentPropsWithoutRef<typeof ScrollAreaPrimitive.ScrollAreaScrollbar>
    29	>(({ className, orientation = "vertical", ...props }, ref) => (
    30	  <ScrollAreaPrimitive.ScrollAreaScrollbar
    31	    ref={ref}
    32	    orientation={orientation}
    33	    className={cn(
    34	      "flex touch-none select-none transition-colors",
    35	      orientation === "vertical" &&
    36	        "h-full w-2.5 border-l border-l-transparent p-[1px]",
    37	      orientation === "horizontal" &&
    38	        "h-2.5 flex-col border-t border-t-transparent p-[1px]",
    39	      className
    40	    )}
    41	    {...props}
    42	  >
    43	    <ScrollAreaPrimitive.ScrollAreaThumb className="relative flex-1 rounded-full bg-line" />
    44	  </ScrollAreaPrimitive.ScrollAreaScrollbar>
    45	))
    46	ScrollBar.displayName = ScrollAreaPrimitive.ScrollAreaScrollbar.displayName
    47	
    48	export { ScrollArea, ScrollBar }