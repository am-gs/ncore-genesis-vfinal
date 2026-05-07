     1	// Dialog component
     2	
     3	"use client"
     4	
     5	import * as React from "react"
     6	import * as DialogPrimitive from "@radix-ui/react-dialog"
     7	import { Cross2Icon } from "@radix-ui/react-icons"
     8	
     9	import { cn } from "@/app/lib/utils"
    10	
    11	const Dialog = DialogPrimitive.Root
    12	
    13	const DialogTrigger = DialogPrimitive.Trigger
    14	
    15	const DialogPortal = DialogPrimitive.Portal
    16	
    17	const DialogClose = DialogPrimitive.Close
    18	
    19	const DialogOverlay = React.forwardRef<
    20	  React.ElementRef<typeof DialogPrimitive.Overlay>,
    21	  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
    22	>(({ className, ...props }, ref) => (
    23	  <DialogPrimitive.Overlay
    24	    ref={ref}
    25	    className={cn(
    26	      "fixed inset-0 z-50 bg-black/80  data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
    27	      className
    28	    )}
    29	    {...props}
    30	  />
    31	))
    32	DialogOverlay.displayName = DialogPrimitive.Overlay.displayName
    33	
    34	const DialogContent = React.forwardRef<
    35	  React.ElementRef<typeof DialogPrimitive.Content>,
    36	  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
    37	>(({ className, children, ...props }, ref) => (
    38	  <DialogPortal>
    39	    <DialogOverlay />
    40	    <DialogPrimitive.Content
    41	      ref={ref}
    42	      className={cn(
    43	        "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border border-line bg-panel p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg",
    44	        className
    45	      )}
    46	      {...props}
    47	    >
    48	      {children}
    49	      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground">
    50	        <Cross2Icon className="h-4 w-4" />
    51	        <span className="sr-only">Close</span>
    52	      </DialogPrimitive.Close>
    53	    </DialogPrimitive.Content>
    54	  </DialogPortal>
    55	))
    56	DialogContent.displayName = DialogPrimitive.Content.displayName
    57	
    58	const DialogHeader = ({
    59	  className,
    60	  ...props
    61	}: React.HTMLAttributes<HTMLDivElement>) => (
    62	  <div
    63	    className={cn(
    64	      "flex flex-col space-y-1.5 text-center sm:text-left",
    65	      className
    66	    )}
    67	    {...props}
    68	  />
    69	)
    70	DialogHeader.displayName = "DialogHeader"
    71	
    72	const DialogFooter = ({
    73	  className,
    74	  ...props
    75	}: React.HTMLAttributes<HTMLDivElement>) => (
    76	  <div
    77	    className={cn(
    78	      "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2",
    79	      className
    80	    )}
    81	    {...props}
    82	  />
    83	)
    84	DialogFooter.displayName = "DialogFooter"
    85	
    86	const DialogTitle = React.forwardRef<
    87	  React.ElementRef<typeof DialogPrimitive.Title>,
    88	  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
    89	>(({ className, ...props }, ref) => (
    90	  <DialogPrimitive.Title
    91	    ref={ref}
    92	    className={cn(
    93	      "text-lg font-semibold leading-none tracking-tight",
    94	      className
    95	    )}
    96	    {...props}
    97	  />
    98	))
    99	DialogTitle.displayName = DialogPrimitive.Title.displayName
   100	
   101	const DialogDescription = React.forwardRef<
   102	  React.ElementRef<typeof DialogPrimitive.Description>,
   103	  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
   104	>(({ className, ...props }, ref) => (
   105	  <DialogPrimitive.Description
   106	    ref={ref}
   107	    className={cn("text-sm text-text-secondary", className)}
   108	    {...props}
   109	  />
   110	))
   111	DialogDescription.displayName = DialogPrimitive.Description.displayName
   112	
   113	export {
   114	  Dialog,
   115	  DialogPortal,
   116	  DialogOverlay,
   117	  DialogTrigger,
   118	  DialogClose,
   119	  DialogContent,
   120	  DialogHeader,
   121	  DialogFooter,
   122	  DialogTitle,
   123	  DialogDescription,
   124	}