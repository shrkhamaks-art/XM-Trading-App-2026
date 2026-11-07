import { cookies } from 'next/headers';

export const dynamic = 'force-dynamic';

export default async function Admin() {
  const session = (await cookies()).get('__Host-session')?.value;
  let data, message = 'سجّل الدخول بحساب إداري لعرض الملخص.';
  if (session && /^[A-Za-z0-9_-]+$/.test(session)) {
    try {
      const origin = process.env.TRADE_STUDIO_BACKEND_ORIGIN || 'http://127.0.0.1:8000';
      const response = await fetch(new URL('/api/admin/summary', origin), {
        cache: 'no-store',
        redirect: 'error',
        signal: AbortSignal.timeout(5000),
        headers: { Cookie: '__Host-session=' + session },
      });
      if (response.ok) data = await response.json();
      else if (response.status === 403) message = 'هذا الحساب لا يملك صلاحية الإدارة.';
      else if (response.status !== 401) message = 'تعذّر جلب ملخص الإدارة.';
    } catch {
      message = 'تعذّر الاتصال بخادم الإدارة.';
    }
  }
  return (
    <main>
      <header><strong>Trade Studio</strong></header>
      <section>
        <h1>ملخص الإدارة</h1>
        {data ? <dl><dt>حسابات المستخدمين</dt><dd>{data.users}</dd><dt>الجلسات النشطة</dt><dd>{data.active_sessions}</dd></dl>
          : <p>{message}</p>}
        <a className="primary" href="/app">فتح الحساب</a>
      </section>
    </main>
  );
}
