import "./globals.css";
import Providers from "./providers";

export const metadata = {
  title: "Visual Stock",
  description: "History Repeats Itself",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
