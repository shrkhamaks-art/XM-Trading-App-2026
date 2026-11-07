import './style.css';

export const metadata = {
  title: 'Trade Studio',
  description: 'واجهة Trade Studio للحساب ومعاينة التداول',
};

export default function RootLayout({ children }) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>;
}
