import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DataSentry | Dataset Quality Workspace",
  description:
    "Profile datasets, inspect data quality, and prepare reliable machine-learning workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
