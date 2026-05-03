import "@/styles/globals.css";
import Footer, { AdminProvider } from "./footer";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex flex-col min-h-screen">
        <AdminProvider>
          <div className="flex-1">{children}</div>
          <Footer />
        </AdminProvider>
      </body>
    </html>
  );
}
