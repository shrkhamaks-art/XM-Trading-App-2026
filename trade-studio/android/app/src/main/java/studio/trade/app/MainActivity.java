package studio.trade.app;

import android.app.Activity;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.WindowInsets;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        Uri origin = Uri.parse(BuildConfig.APP_URL);
        WebView browser = new WebView(this);
        browser.getSettings().setJavaScriptEnabled(true);
        browser.getSettings().setAllowFileAccess(false);
        browser.getSettings().setAllowContentAccess(false);
        browser.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri url = request.getUrl();
                return !"https".equals(url.getScheme())
                        || !origin.getHost().equalsIgnoreCase(url.getHost())
                        || effectivePort(origin) != effectivePort(url);
            }
        });
        if (Build.VERSION.SDK_INT >= 30) {
            browser.setOnApplyWindowInsetsListener((view, insets) -> {
                android.graphics.Insets bars = insets.getInsets(WindowInsets.Type.systemBars());
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
                return insets;
            });
        }
        setContentView(browser);
        browser.loadUrl(BuildConfig.APP_URL);
    }

    private static int effectivePort(Uri url) {
        return url.getPort() == -1 ? 443 : url.getPort();
    }
}
