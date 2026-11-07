import 'package:flutter_test/flutter_test.dart';
import 'package:trade_studio/api.dart';

void main() {
  test('only an HTTPS origin is accepted', () {
    for (final url in [
      '',
      'http://example.com',
      'https://u@example.com',
      'https://example.com/path',
      'https://example.com/?x=1',
    ]) {
      final api = StudioApi(url);
      expect(api.configured, isFalse, reason: url);
      api.close();
    }
    final api = StudioApi('https://example.com');
    expect(api.configured, isTrue);
    api.close();
  });
}
