import { Toaster as SonnerToaster } from "sonner";

interface ToasterProps {
  appearance: "light" | "dark";
}

export function Toaster({ appearance }: ToasterProps) {
  return (
    <SonnerToaster
      position="bottom-center"
      closeButton
      theme={appearance}
      style={{ zIndex: 2147483647 }}
    />
  );
}
