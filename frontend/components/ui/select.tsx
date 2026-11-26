"use client";

import * as React from "react";
import { Select as SelectPrimitive } from "@base-ui/react/select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "cn";

const Select = SelectPrimitive.Root;

const SelectGroup = SelectPrimitive.Group;

const SelectValue = SelectPrimitive.Value;

function SelectTrigger({ className, children, ...props }: SelectPrimitive.Trigger.Props) {
  return (
    <SelectPrimitive.Trigger
      className={cn(
        "flex h-9 w-full items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 py-2 text-sm font-medium shadow-2xs outline-none transition-colors hover:bg-muted/50 focus:border-ring focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 cursor-pointer",
        className
      )}
      {...props}
    >
      <div className="flex items-center gap-2 min-w-0 flex-1 truncate text-left">{children}</div>
      <SelectPrimitive.Icon className="shrink-0 flex items-center justify-center">
        <ChevronDown className="h-4 w-4 opacity-50" />
      </SelectPrimitive.Icon>
    </SelectPrimitive.Trigger>
  );
}

function SelectPortal({ children, ...props }: SelectPrimitive.Portal.Props) {
  return <SelectPrimitive.Portal {...props}>{children}</SelectPrimitive.Portal>;
}

function SelectPositioner({ className, children, ...props }: SelectPrimitive.Positioner.Props) {
  return (
    <SelectPrimitive.Positioner
      sideOffset={6}
      className={cn("z-50 outline-none", className)}
      {...props}
    >
      {children}
    </SelectPrimitive.Positioner>
  );
}

function SelectPopup({ className, children, ...props }: SelectPrimitive.Popup.Props) {
  return (
    <SelectPrimitive.Popup
      className={cn(
        "relative max-h-96 min-w-[16rem] overflow-hidden rounded-xl border border-border bg-popover p-1.5 text-popover-foreground shadow-md transition-all outline-none animate-in fade-in-80",
        className
      )}
      {...props}
    >
      <SelectPrimitive.List className="overflow-y-auto max-h-80 space-y-0.5 outline-none">
        {children}
      </SelectPrimitive.List>
    </SelectPrimitive.Popup>
  );
}

function SelectItem({ className, children, ...props }: SelectPrimitive.Item.Props) {
  return (
    <SelectPrimitive.Item
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center rounded-lg py-2 pl-3 pr-8 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
        className
      )}
      {...props}
    >
      <SelectPrimitive.ItemText className="flex-1 truncate">{children}</SelectPrimitive.ItemText>
      <SelectPrimitive.ItemIndicator className="absolute right-2.5 flex h-3.5 w-3.5 items-center justify-center">
        <Check className="h-4 w-4 text-primary" />
      </SelectPrimitive.ItemIndicator>
    </SelectPrimitive.Item>
  );
}

function SelectSeparator({ className, ...props }: SelectPrimitive.Separator.Props) {
  return (
    <SelectPrimitive.Separator className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />
  );
}

export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectPortal,
  SelectPositioner,
  SelectPopup,
  SelectItem,
  SelectSeparator,
};
