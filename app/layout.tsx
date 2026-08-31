import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MMI by Monitoring | Memoria técnica inteligente",
  description: "Conecte SAP PM, FMECA y conocimiento experto para convertir información dispersa en decisiones de mantenimiento respaldadas por evidencia.",
  other: {
    "codex-preview": "development",
  },
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body className="antialiased">{children}</body>
    </html>
  );
}
