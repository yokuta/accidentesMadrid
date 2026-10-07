import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "A pie · Madrid",
  description: "Compara calles, comparte tu percepción y descubre su accidentalidad peatonal registrada.",
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
