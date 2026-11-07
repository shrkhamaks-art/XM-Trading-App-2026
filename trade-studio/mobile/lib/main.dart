import 'package:flutter/material.dart';

import 'api.dart';

void main() => runApp(const TradeStudio());

class TradeStudio extends StatelessWidget {
  const TradeStudio({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Trade Studio',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xffe92035),
          brightness: Brightness.dark,
        ),
        scaffoldBackgroundColor: const Color(0xff0b0e12),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
        ),
      ),
      home: const StudioScreen(),
    );
  }
}

class StudioScreen extends StatefulWidget {
  const StudioScreen({super.key});

  @override
  State<StudioScreen> createState() => _StudioScreenState();
}

class _StudioScreenState extends State<StudioScreen> {
  final _api = StudioApi(const String.fromEnvironment('TRADE_STUDIO_URL'));
  final _email = TextEditingController();
  final _code = TextEditingController();
  bool _english = false, _busy = false, _codeSent = false;
  int _tab = 0;
  String? _account, _notice;
  Map<String, dynamic>? _quote;

  String t(String ar, String en) => _english ? en : ar;

  Future<void> _perform(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _notice = null;
    });
    try {
      await action();
    } on ApiFailure catch (error) {
      if (mounted)
        setState(
          () => _notice = _english
              ? 'The request could not be completed.'
              : error.message,
        );
    } on Exception {
      if (mounted)
        setState(
          () => _notice = t(
            'تعذّر الاتصال بالخادم.',
            'Could not reach the server.',
          ),
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _login() => _perform(() async {
    final email = _email.text.trim();
    if (_codeSent) {
      final code = _code.text.trim();
      if (!RegExp(r'^[0-9]{6}$').hasMatch(code)) {
        throw const ApiFailure('أدخل رمز التحقق المكوّن من ستة أرقام.');
      }
      final result = await _api.request('verify', {
        'email': email,
        'code': code,
      });
      if (mounted) setState(() => _account = result['email'] as String);
    } else {
      await _api.request('code', {'email': email});
      if (mounted)
        setState(() {
          _codeSent = true;
          _notice = t(
            'راجع بريدك لاستلام الرمز.',
            'Check your email for the code.',
          );
        });
    }
  });

  void _logout(bool all) => _perform(() async {
    await _api.request(all ? 'logout-all' : 'logout', {});
    if (mounted)
      setState(() {
        _account = null;
        _codeSent = false;
        _code.clear();
      });
  });

  void _loadQuote() => _perform(() async {
    setState(() => _quote = null);
    final data = await _api.request('markets/btc-usd');
    if (mounted) setState(() => _quote = data);
  });

  @override
  void dispose() {
    _email.dispose();
    _code.dispose();
    _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: _english ? TextDirection.ltr : TextDirection.rtl,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Trade Studio'),
          actions: [
            TextButton(
              onPressed: () => setState(() {
                _english = !_english;
                _notice = null;
              }),
              child: Text(t('EN', 'العربية')),
            ),
          ],
        ),
        body: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            if (!_api.configured)
              Text(
                t(
                  'لم يُضبط عنوان خادم HTTPS لهذه النسخة.',
                  'This build has no HTTPS server configured.',
                ),
              ),
            const SizedBox(height: 16),
            if (_tab == 0) ..._accountPanel() else ..._marketPanel(),
            if (_busy) const LinearProgressIndicator(),
            if (_notice case final notice?)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(notice, semanticsLabel: notice),
              ),
          ],
        ),
        bottomNavigationBar: NavigationBar(
          selectedIndex: _tab,
          onDestinationSelected: (index) {
            setState(() {
              _tab = index;
              _notice = null;
            });
          },
          destinations: [
            NavigationDestination(
              icon: const Icon(Icons.person_outline),
              label: t('الحساب', 'Account'),
            ),
            NavigationDestination(
              icon: const Icon(Icons.show_chart),
              label: t('السوق', 'Market'),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _accountPanel() {
    if (_account case final account?) {
      return [
        Text(account, textDirection: TextDirection.ltr),
        TextButton(
          onPressed: _busy ? null : () => _logout(false),
          child: Text(t('تسجيل الخروج', 'Sign out')),
        ),
        TextButton(
          onPressed: _busy ? null : () => _logout(true),
          child: Text(t('الخروج من جميع الأجهزة', 'Sign out everywhere')),
        ),
      ];
    }
    return [
      Text(
        t('تسجيل الدخول بالبريد', 'Email sign-in'),
        style: Theme.of(context).textTheme.headlineSmall,
      ),
      const SizedBox(height: 16),
      TextField(
        controller: _email,
        readOnly: _codeSent || _busy,
        keyboardType: TextInputType.emailAddress,
        textDirection: TextDirection.ltr,
        decoration: InputDecoration(
          labelText: t('البريد الإلكتروني', 'Email address'),
        ),
      ),
      if (_codeSent) ...[
        const SizedBox(height: 12),
        TextField(
          controller: _code,
          keyboardType: TextInputType.number,
          maxLength: 6,
          decoration: InputDecoration(
            labelText: t('رمز التحقق', 'Verification code'),
          ),
        ),
        TextButton(
          onPressed: _busy
              ? null
              : () => setState(() {
                  _codeSent = false;
                  _code.clear();
                }),
          child: Text(
            t(
              'تغيير البريد أو طلب رمز جديد',
              'Change email or request a new code',
            ),
          ),
        ),
      ],
      const SizedBox(height: 12),
      FilledButton(
        onPressed: _busy || !_api.configured ? null : _login,
        child: Text(
          _codeSent ? t('تحقق', 'Verify') : t('إرسال الرمز', 'Send code'),
        ),
      ),
    ];
  }

  List<Widget> _marketPanel() {
    final quote = _quote;
    return [
      const Text('BTC-USD', textDirection: TextDirection.ltr),
      if (quote != null) ...[
        Text('USD ${quote['price']}', textDirection: TextDirection.ltr),
        Text(
          '${quote['provider']} · ${quote['time']}',
          textDirection: TextDirection.ltr,
        ),
      ] else
        Text(t('لا يوجد سعر محمّل.', 'No price loaded.')),
      OutlinedButton(
        onPressed: _busy || !_api.configured ? null : _loadQuote,
        child: Text(t('تحديث السعر', 'Refresh price')),
      ),
    ];
  }
}
