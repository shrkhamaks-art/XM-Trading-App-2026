# تعليمات بناء التطبيق والتحقق منه

1. ارفع **محتويات** مجلد XM_Trading_Phase6 إلى جذر مستودع GitHub خاص.
2. افتح Actions ثم Backend checks وشغّل المسار، وراجع نجاح PostgreSQL 16 وترحيلات Alembic والاختبارات.
3. افتح Android sandbox debug build ثم Run workflow.
4. يفحص المسار APK باستخدام aapt وSHA256 ثم يحاول تثبيته وفتح MainActivity على محاكي Android 35.
5. عند النجاح نزّل xm-trading-sandbox-debug-apk من Artifacts. يوجد سجل مستقل باسم xm-trading-android-evidence.

**تنبيه:** هذه إجراءات إعداد وتشغيل آلي ولم تُنفذ على GitHub من هذه البيئة. التطبيق تجريبي تقنيًا حتى تحقق التفويض والامتثال وربط الخدمات الحقيقية. لا توجد خدمات تداول أو تحويل أموال حقيقية.
